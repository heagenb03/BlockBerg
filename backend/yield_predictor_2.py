"""
Yield predictor for RWA (Real World Asset) treasury tokens.

Loads token price/time-series data from CSV, cleans and scales it, then trains
an LSTM model to predict the next value for each token. Uses the last 365 days
of data per token; first 4 tokens for training, 5th for testing.
"""
import requests
import rwapipe_client
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense


def clean_timeseries(timeseries):
    """
    Remove invalid entries and convert a timeseries to a list of floats.

    Drops empty strings, the string 'nan', and pandas/float NaN values so that
    only valid numeric values remain. Used before scaling and model training.

    Args:
        timeseries: List (or list-like) of values, e.g. from a DataFrame column.
            May contain strings, floats, or pandas NA types.

    Returns:
        List of float: only valid numeric values, in original order.
    """
    return [float(x) for x in timeseries if x != '' and x != 'nan' and not pd.isna(x)]


def daily_yield_from_values(values):
    """
    Compute daily (total) yield from a timeseries of daily total values.

    Daily yield = (Value_t - Value_{t-1}) / Value_{t-1}, i.e. the day-over-day
    return. For tokenized US Treasuries, this is the daily return on the
    portfolio/token total value. First day has no prior value, so its yield
    is NaN.

    Args:
        values: Array-like of floats, daily total value (e.g. one token or
            sum across tokens). Length n.

    Returns:
        np.ndarray: Daily yields, length n. First element is np.nan; rest are
            (values[1:] - values[:-1]) / values[:-1].
    """
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return np.array([np.nan] * len(values))
    y = np.empty_like(values)
    y[0] = np.nan
    y[1:] = (values[1:] - values[:-1]) / values[:-1]
    return y


def get_all_timeseries_data(token_timeseries):
    """
    Extract and clean the last 365 days of data for five treasury token columns.

    Reads five fixed token columns from the provided DataFrame, cleans each
    series with clean_timeseries(), then returns the data in two layouts:
    - extended: one long list (all five series concatenated) for fitting scaler.
    - appended: list of five lists (one per token) for train/test splitting.

    Args:
        token_timeseries: pandas DataFrame with columns for each token. Must
            include: 'OpenTrade Flexible Term USD Vault (Ethereum)', 'OpenEden
            TBILL Vault', 'Backed ZPR1 $ 1-3 Month T-Bill', 'BlackRock USD
            Institutional Digital Liquidity Fund', 'Guggenheim Treasury Services DCP'.

    Returns:
        tuple: (all_timeseries_data_extended, all_timeseries_data_appended)
            - extended: flat list of floats (all tokens, last 365 days each).
            - appended: list of 5 lists, each list is one token's last 365 values.
    """
    all_timeseries_data_extended = []
    all_timeseries_data_appended = []

    timeseries_1 = token_timeseries['OpenTrade Flexible Term USD Vault (Ethereum)'].tolist()
    timeseries_2 = token_timeseries['OpenEden TBILL Vault'].tolist()
    timeseries_3 = token_timeseries['Backed ZPR1 $ 1-3 Month T-Bill'].tolist()
    timeseries_4 = token_timeseries['BlackRock USD Institutional Digital Liquidity Fund'].tolist()
    timeseries_5 = token_timeseries['Guggenheim Treasury Services DCP'].tolist()

    # Clean each series and keep only the last 365 days for modeling
    timeseries_1 = clean_timeseries(timeseries_1)[-365:]
    timeseries_2 = clean_timeseries(timeseries_2)[-365:]
    timeseries_3 = clean_timeseries(timeseries_3)[-365:]
    timeseries_4 = clean_timeseries(timeseries_4)[-365:]
    timeseries_5 = clean_timeseries(timeseries_5)[-365:]

    # Extended: one flat list (used to fit MinMaxScaler on full range of values)
    all_timeseries_data_extended.extend(timeseries_1)
    all_timeseries_data_extended.extend(timeseries_2)
    all_timeseries_data_extended.extend(timeseries_3)
    all_timeseries_data_extended.extend(timeseries_4)
    all_timeseries_data_extended.extend(timeseries_5)

    # Appended: list of 5 lists (one per token) for train/test split
    all_timeseries_data_appended.append(timeseries_1)
    all_timeseries_data_appended.append(timeseries_2)
    all_timeseries_data_appended.append(timeseries_3)
    all_timeseries_data_appended.append(timeseries_4)
    all_timeseries_data_appended.append(timeseries_5)

    return all_timeseries_data_extended, all_timeseries_data_appended


def scale_timeseries(all_timeseries_data_extended, all_timeseries_data_appended):
    """
    Scale all timeseries to [0, 1] using MinMaxScaler.

    Fits the scaler on the extended (concatenated) data so the same min/max
    applies across all tokens, then transforms both the extended list and each
    of the appended series. Required for LSTM input and stable training.

    Args:
        all_timeseries_data_extended: Flat list of floats (all tokens combined).
        all_timeseries_data_appended: List of 5 lists, each one token's values.

    Returns:
        tuple: (all_scaled_timeseries_data_extended, all_scaled_timeseries_data_appended, timeseries_scaler)
            - extended: (n, 1) array, scaled.
            - appended: array of 5 (n_i, 1) arrays, scaled.
            - timeseries_scaler: fitted MinMaxScaler for inverse_transform later.
    """
    # Reshape to (n, 1): MinMaxScaler expects 2D input
    all_timeseries_data_extended_array = np.array(all_timeseries_data_extended).reshape(-1, 1)
    all_timeseries_data_appended_array = np.array([
        np.array(ts).reshape(-1, 1)
        for ts in all_timeseries_data_appended
    ])

    timeseries_scaler = MinMaxScaler()
    all_scaled_timeseries_data_extended = timeseries_scaler.fit_transform(all_timeseries_data_extended_array)
    # Transform each token series with the same fitted scaler
    all_scaled_timeseries_data_appended = np.array([
        timeseries_scaler.transform(ts.reshape(-1, 1))
        for ts in all_timeseries_data_appended_array
    ])

    return all_scaled_timeseries_data_extended, all_scaled_timeseries_data_appended, timeseries_scaler


def get_train_test_data(all_scaled_timeseries_data_appended, timeseries_scaler):
    """
    Split scaled data into train (first 4 tokens) and test (5th token).

    For each series, uses all but the last time step as input (X) and the last
    step as target (y). Unscales y_test with the provided scaler for evaluation.

    Args:
        all_scaled_timeseries_data_appended: Array of 5 scaled timeseries arrays.
        timeseries_scaler: Fitted MinMaxScaler used to inverse_transform y_test.

    Returns:
        tuple: (X_train, y_train, X_test, y_test, unscaled_y_test)
            - X_train, y_train: inputs/targets for training (4 tokens).
            - X_test, y_test: inputs/targets for testing (1 token), scaled.
            - unscaled_y_test: y_test in original value scale for metrics.
    """
    train = all_scaled_timeseries_data_appended[:4]   # first 4 tokens
    test = all_scaled_timeseries_data_appended[4:]   # 5th token
    # For each series: X = all steps except last, y = last step (next-value prediction)
    X_train = np.array([indv_train[:-1] for indv_train in train])
    y_train = np.array([indv_train[-1:] for indv_train in train])
    X_test = np.array([indv_test[:-1] for indv_test in test])
    y_test = np.array([indv_test[-1:] for indv_test in test])
    unscaled_y_test = np.array([timeseries_scaler.inverse_transform(t) for t in y_test])
    return X_train, y_train, X_test, y_test, unscaled_y_test


def build_model(X_train, y_train):
    """
    Build and train a two-layer LSTM model for next-step prediction.

    Architecture: LSTM(50, return_sequences=True) -> LSTM(50) -> Dense(1).
    Trained with Adam and MSE loss for 100 epochs, batch size 32.

    Args:
        X_train: Training inputs, shape (n_samples, seq_len, 1).
        y_train: Training targets, shape (n_samples, 1).

    Returns:
        keras.Model: Fitted Sequential model.
    """
    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=(X_train.shape[1], 1)))
    model.add(LSTM(50))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(X_train, y_train, epochs=100, batch_size=32)
    return model

def make_predictions(model, X_test, y_test, unscaled_y_test, timeseries_scaler):
    """
    Run the model on test data and inverse-scale predictions to original units.

    Prints predictions, scaled y_test, and unscaled y_test for comparison.

    Args:
        model: Fitted Keras model.
        X_test: Test inputs.
        y_test: Test targets (scaled).
        unscaled_y_test: Test targets in original scale.
        timeseries_scaler: MinMaxScaler used to inverse_transform predictions.

    Returns:
        np.ndarray: Predictions in original value scale.
    """
    predictions = model.predict(X_test)
    predictions = timeseries_scaler.inverse_transform(predictions)
    print(f"predictions: {predictions}")
    print(f"y_test: {y_test}")
    print(f"unscaled_y_test: {unscaled_y_test}")

    return predictions

def main():
    """
    End-to-end pipeline: load data, clean, scale, train LSTM, and predict.

    Fetches market/treasury metadata (optional), loads token CSV, extracts and
    cleans five token series (last 365 days), scales with MinMaxScaler, splits
    into train (tokens 1–4) and test (token 5), trains LSTM, and returns
    predictions in original scale.
    """
    # Optional: fetch market overview and treasury token list (currently unused in pipeline)
    response = requests.get("https://rwapipe.com/api/market", timeout=30.0)
    treasury_tokens = rwapipe_client.get_treasury_tokens_from_market()

    # Load token timeseries from CSV (required)
    token_timeseries = pd.read_csv('rwa-token-timeseries-export-1772849815861.csv')

    # Extract last 365 days per token, in extended and appended layouts
    all_timeseries_data_extended, all_timeseries_data_appended = get_all_timeseries_data(token_timeseries)

    # Scale all series to [0, 1] and keep scaler for inverse_transform
    all_scaled_timeseries_data_extended, all_scaled_timeseries_data_appended, timeseries_scaler = scale_timeseries(
        all_timeseries_data_extended, all_timeseries_data_appended
    )

    # Train on first 4 tokens, test on 5th; X = all but last step, y = last step
    X_train, y_train, X_test, y_test, unscaled_y_test = get_train_test_data(
        all_scaled_timeseries_data_appended, timeseries_scaler
    )

    model = build_model(X_train, y_train)
    predictions = make_predictions(model, X_test, y_test, unscaled_y_test, timeseries_scaler)

    return predictions

    '''for item in all_scaled_timeseries_data_appended:
        print(f"item: {item[:5]}")
        print(f"type of item: {type(item)}")'''




    # print(f"all_scaled_timeseries_data: {all_scaled_timeseries_data[:5]}")


    '''print(f"token_timeseries: {type(timeseries_1)}")
    print(f"token_timeseries: {timeseries_1[-5:]}")
    print(f"type of timeseries_1: {type(timeseries_1)}")

    # print lengths of each timeseries
    print(f"length of timeseries_1: {len(timeseries_1)}")
    print(f"length of timeseries_2: {len(timeseries_2)}")
    print(f"length of timeseries_3: {len(timeseries_3)}")
    print(f"length of timeseries_4: {len(timeseries_4)}")
    print(f"length of timeseries_5: {len(timeseries_5)}")

    # print the first 5 elements of each timeseries
    print(f"first 5 elements of timeseries_1: {timeseries_1[:5]}")
    print(f"first 5 elements of timeseries_2: {timeseries_2[:5]}")
    print(f"first 5 elements of timeseries_3: {timeseries_3[:5]}")
    print(f"first 5 elements of timeseries_4: {timeseries_4[:5]}")
    print(f"first 5 elements of timeseries_5: {timeseries_5[:5]}")'''

if __name__ == "__main__":
    main()