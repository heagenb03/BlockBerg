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
from sklearn.preprocessing import StandardScaler


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
    print(f"len of timeseries: {len(timeseries)}")
    if len(timeseries) <= 20:
        # return the same timeseries as the return in try, but remove the '%' character in every value 
        #print(f"timeseries: {timeseries}")
        timeseries = [x.replace('%', '') if len(str(x)) >= 4 else x for x in timeseries]
        #print(f"timeseries: {timeseries}")
        new_timeseries = [float(x) for x in timeseries if x != '' and x != 'nan' and not pd.isna(x)]
        #print(f"new_timeseries: {new_timeseries}")
        return new_timeseries
    try:
        return [float(x) for x in timeseries if x != '' and x != 'nan' and not pd.isna(x) and type(x) == float]
    except Exception as e:
        print(f"Error cleaning timeseries: {e}. Skipping first row.")

        return timeseries[1:]




def create_and_clean_timeseries(timeseries_df, num_days, indices, names):

    timeseries_list = []
    # Holds the indices of the tokens and token names that have enough data and are in the names list
    counter_list = []
    name_list = []
    # Extract all days of yield timeseries for every token in yield_timeseries
    counter = 0
    for token in timeseries_df.columns:
        cleaned_timeseries = clean_timeseries(timeseries_df[token].tolist())
        if len(cleaned_timeseries) < num_days:
            print(f"Token {token} has less than {num_days} days of data, skipping")
            continue
        timeseries_list.append(cleaned_timeseries[-num_days:])
        if token in names:
            counter_list.append(counter)
        # name_list.append(names[counter])
        counter += 1
    return timeseries_list, counter_list, names


def get_all_timeseries_data(token_timeseries, num_days, indices, names):
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

    timeseries_list, counter_list, name_list = create_and_clean_timeseries(token_timeseries, num_days, indices, names)
    for timeseries in timeseries_list:
        all_timeseries_data_extended.extend(timeseries)
        all_timeseries_data_appended.append(timeseries)

    return all_timeseries_data_extended, all_timeseries_data_appended, counter_list, name_list


def scale_timeseries(all_timeseries_data_extended, all_timeseries_data_appended):
    """
    Scale all timeseries to [0, 1] using MinMaxScaler.

    Fits the scaler on the extended (concatenated) data so the same min/max
    applies across all tokens, then transforms both the extended list and each
    of the appended series. Required for LSTM input and stable training.

    Args:
        all_timeseries_data_extended: Flat list of floats (all tokens combined).
        all_timeseries_data_appended: List of num_tokens lists, each one token's values.

    Returns:
        tuple: (all_scaled_timeseries_data_extended, all_scaled_timeseries_data_appended, timeseries_scaler)
            - extended: (n, 1) array, scaled.
            - appended: array of num_tokens (n_i, 1) arrays, scaled.
            - timeseries_scaler: fitted MinMaxScaler for inverse_transform later.
    """
    # Reshape to (n, 1): MinMaxScaler expects 2D input
    all_timeseries_data_extended_array = np.array(all_timeseries_data_extended).reshape(-1, 1)
    all_timeseries_data_appended_array = np.array([
        np.array(ts).reshape(-1, 1)
        for ts in all_timeseries_data_appended
    ])

    # timeseries_scaler = MinMaxScaler()
    timeseries_scaler = StandardScaler()
    all_scaled_timeseries_data_extended = timeseries_scaler.fit_transform(all_timeseries_data_extended_array)
    # Transform each token series with the same fitted scaler
    all_scaled_timeseries_data_appended = np.array([
        timeseries_scaler.transform(ts.reshape(-1, 1))
        for ts in all_timeseries_data_appended_array
    ])

    return all_scaled_timeseries_data_extended, all_scaled_timeseries_data_appended, timeseries_scaler


def get_train_test_data(all_scaled_timeseries_data_appended, timeseries_scaler, indices, names):
    not_in_indices = [i for i in range(len(all_scaled_timeseries_data_appended)) if i not in indices]
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
    # These tokens are the ones we want to predict in both the token and yield pipelines
    # BlackRock BUIDL, Circle USYC, Ondo U.S. Dollar Yield, Franklin OnChain, WisdomTree Gov MMF

    train = [all_scaled_timeseries_data_appended[i] for i in not_in_indices]   # training tokens
    test = [all_scaled_timeseries_data_appended[i] for i in indices]   # predicting tokens
    # For each series: X = all steps except last, y = last step (next-value prediction)
    X_train = np.array([indv_train[:-3] for indv_train in train])
    y_train = np.array([indv_train[-3:] for indv_train in train])
    X_test = np.array([indv_test[3:] for indv_test in test]) # Changed from [:-3] to [3:] to get the last 3 days of data for the predicting tokens
    y_test = np.array([indv_test[-3:] for indv_test in test])
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
    model.add(Dense(3))
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(X_train, y_train, epochs=100, batch_size=32)
    return model

def make_predictions(model, X_test, y_test, unscaled_y_test, timeseries_scaler, names):
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
    print(f"X_test: {X_test}")
    #print(f"y_test: {y_test}")
    print(f"unscaled_y_test: {unscaled_y_test}")
    predictions = model.predict(X_test)
    predictions = timeseries_scaler.inverse_transform(predictions)
    for i, prediction in enumerate(predictions):
        print(f"Index {names[i]} predictions (Next 3 Days): {prediction}")
    return predictions

def main_pipeline(days_of_data, timeseries_df, indices, names):
    """
    End-to-end pipeline: load data, clean, scale, train LSTM, and predict.

    Fetches market/treasury metadata (optional), loads token CSV, extracts and
    cleans five token series (last 365 days), scales with MinMaxScaler, splits
    into train (tokens 1–4) and test (token 5), trains LSTM, and returns
    predictions in original scale.
    """
    # Optional: fetch market overview and treasury token list (currently unused in pipeline)
    '''response = requests.get("https://rwapipe.com/api/market", timeout=30.0)
    treasury_tokens = rwapipe_client.get_treasury_tokens_from_market()'''

    # Extract last x days per token, in extended and appended layouts
    all_timeseries_data_extended, all_timeseries_data_appended, cleaned_indices_list, cleaned_name_list = get_all_timeseries_data(timeseries_df, days_of_data, indices, names)
    # get the last x days of data for the indices
    # Commented out two lines below because the indices should only be used for X and y training/testing, not for scaling
    # all_timeseries_data_extended = [all_timeseries_data_extended[i] for i in indices]
    # all_timeseries_data_appended = [all_timeseries_data_appended[i] for i in indices]
    
    # get the names of the tokens
    # WHy are we even doing this? 
    # names = [names[i] for i in indices]

    # Scale all series to [0, 1] and keep scaler for inverse_transform
    all_scaled_timeseries_data_extended, all_scaled_timeseries_data_appended, timeseries_scaler = scale_timeseries(
        all_timeseries_data_extended, all_timeseries_data_appended
    )

    # Calculate the indices of the tokens in the all_scaled_timeseries_data_appended

    print(f"all columns: {timeseries_df.columns.tolist()}")
    print(f"cleaned_indices_list: {cleaned_indices_list}")
    print(f"cleaned_name_list: {cleaned_name_list}")

    # Train on first 4 tokens, test on 5th; X = all but last step, y = last step
    X_train, y_train, X_test, y_test, unscaled_y_test = get_train_test_data(
        all_scaled_timeseries_data_appended, timeseries_scaler, cleaned_indices_list, cleaned_name_list
    )

    print(f"X_train shape: {X_train.shape}")
    print(f"y_train shape: {y_train.shape}")
    print(f"X_test shape: {X_test.shape}")
    print(f"y_test shape: {y_test.shape}")
    print(f"unscaled_y_test shape: {unscaled_y_test.shape}")
    # return

    model = build_model(X_train, y_train)
    predictions = make_predictions(model, X_test, y_test, unscaled_y_test, timeseries_scaler, names)

    return predictions


def main():
    # Load token timeseries from CSV (required)
    token_timeseries = pd.read_csv('rwa-token-timeseries-export-1772849815861.csv')

    # Load yield timeseries from CSV (required)
    yield_timeseries = pd.read_csv('daily_yields_2-19-26_to_3-6-26.csv')
    # transpose the yield_timeseries
    yield_timeseries = yield_timeseries.transpose()
    # The first row is the column names, so we need to remove it and add it to a column name list
    column_names = yield_timeseries.iloc[0].tolist()
    yield_timeseries = yield_timeseries.iloc[1:]
    yield_timeseries.columns = column_names

    # These tokens are the ones we want to predict in both the token and yield pipelines
    # BlackRock BUIDL, Circle USYC, Ondo U.S. Dollar Yield, Franklin OnChain, WisdomTree Gov MMF
    token_names = ['BlackRock USD Institutional Digital Liquidity Fund', 'Circle USYC', 'Ondo U.S. Dollar Yield', 'Franklin OnChain U.S. Government Money Fund', 'WisdomTree Government Money Market Digital Fund']
    yield_names = ['BlackRock BUIDL', 'Circle USYC', 'Ondo U.S. Dollar Yield', 'Franklin OnChain', 'WisdomTree Gov MMF']
    # get the indices of the token_tokens in the token_timeseries
    token_indices = [token_timeseries.columns.tolist().index(token) for token in token_names]
    # get the indices of the yield_tokens in the yield_timeseries
    yield_indices = [yield_timeseries.columns.tolist().index(token) for token in yield_names]
    
    # Run the main pipeline
    print("\nRunning token pipeline...")
    token_predictions = main_pipeline(365, token_timeseries, token_indices, token_names)
    print("\nRunning yield pipeline...")
    yield_predictions = main_pipeline(7, yield_timeseries, yield_indices, yield_names)

    #print(f"token_predictions: {token_predictions}")
    #print(f"yield_predictions: {yield_predictions}")

    # RETURNED PREDICTIONS FORMAT
    # token predictions = [[token_1_prediction_day_1, token_1_prediction_day_2, token_1_prediction_day_3], [token_2_prediction_day_1, token_2_prediction_day_2, token_2_prediction_day_3], [token_3_prediction_day_1, token_3_prediction_day_2, token_3_prediction_day_3], [token_4_prediction_day_1, token_4_prediction_day_2, token_4_prediction_day_3], [token_5_prediction_day_1, token_5_prediction_day_2, token_5_prediction_day_3]]
    # yield predictions = [[yield_1_prediction_day_1, yield_1_prediction_day_2, yield_1_prediction_day_3], [yield_2_prediction_day_1, yield_2_prediction_day_2, yield_2_prediction_day_3], [yield_3_prediction_day_1, yield_3_prediction_day_2, yield_3_prediction_day_3], [yield_4_prediction_day_1, yield_4_prediction_day_2, yield_4_prediction_day_3], [yield_5_prediction_day_1, yield_5_prediction_day_2, yield_5_prediction_day_3]]

    # Arrays inside of main prediction list, along with the main list for each prediction array, may (probably) be numpy arrays (for both token and yield predictions)

    return token_predictions, yield_predictions


if __name__ == "__main__":
    main()