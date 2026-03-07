import requests
import rwapipe_client

def main():
    # Get market overview with all tokens
    response = requests.get("https://rwapipe.com/api/market", timeout=30.0)
    # print(response.json())
    # Get treasury tokens from market
    treasury_tokens = rwapipe_client.get_treasury_tokens_from_market()
    print(treasury_tokens[0])

if __name__ == "__main__":
    main()