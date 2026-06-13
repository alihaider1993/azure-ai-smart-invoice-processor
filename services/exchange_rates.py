import requests


def convert_to_gbp(amount: float, currency: str) -> dict:
    """Convert invoice amount to GBP using Frankfurter API."""
    if not amount:
        return {
            "original_amount": amount,
            "original_currency": currency,
            "gbp_amount": 0,
            "exchange_rate": None
        }

    currency = (currency or "GBP").upper()

    if currency == "GBP":
        return {
            "original_amount": amount,
            "original_currency": currency,
            "gbp_amount": amount,
            "exchange_rate": 1
        }

    try:
        response = requests.get(
            "https://api.frankfurter.app/latest",
            params={"amount": amount, "from": currency, "to": "GBP"},
            timeout=10
        )
        response.raise_for_status()
        gbp_amount = response.json()["rates"]["GBP"]

        return {
            "original_amount": amount,
            "original_currency": currency,
            "gbp_amount": round(gbp_amount, 2),
            "exchange_rate": round(gbp_amount / amount, 6)
        }

    except Exception as e:
        return {
            "original_amount": amount,
            "original_currency": currency,
            "gbp_amount": None,
            "exchange_rate": None,
            "currency_warning": f"Currency conversion failed: {e}"
        }
