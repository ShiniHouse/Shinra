import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Mappatura codici WMO Open-Meteo in italiano
WMO_WEATHER_CODES = {
    0: "Cielo sereno",
    1: "Prevalentemente sereno",
    2: "Parzialmente nuvoloso",
    3: "Coperto",
    45: "Nebbia",
    48: "Nebbia con brina",
    51: "Pioggerella leggera",
    53: "Pioggerella moderata",
    55: "Pioggerella densa",
    61: "Pioggia debole",
    63: "Pioggia moderata",
    65: "Pioggia forte",
    71: "Neve debole",
    73: "Neve moderata",
    75: "Neve forte",
    80: "Rovesci di pioggia deboli",
    81: "Rovesci di pioggia moderati",
    82: "Rovesci di pioggia violenti",
    95: "Temporale",
    96: "Temporale con grandine debole",
    99: "Temporale con grandine forte",
}

async def get_weather(location: str = "Roma", days: int = 2) -> Dict[str, Any]:
    """
    Ottiene le previsioni meteo attuali e future (oggi, domani e giorni successivi) per una determinata città o località.
    
    Args:
        location: Nome della città o località (es. 'Roma', 'Milano', 'Firenze').
        days: Numero di giorni di previsione (default 2 per coprire oggi e domani).
    """
    try:
        # 1. Geocodifica gratuita con Open-Meteo Geocoding API
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        async with httpx.AsyncClient(timeout=8.0) as client:
            geo_res = await client.get(geocode_url, params={"name": location, "count": 1, "language": "it", "format": "json"})
            geo_data = geo_res.json()
            
            if not geo_data.get("results"):
                return {"success": False, "message": f"Non sono riuscito a trovare la località '{location}'."}
            
            place = geo_data["results"][0]
            lat = place["latitude"]
            lon = place["longitude"]
            city_name = place.get("name", location)
            country = place.get("country", "")

            # 2. Richiesta meteo
            weather_url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "weather_code", "wind_speed_10m"],
                "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max", "sunrise", "sunset"],
                "timezone": "auto",
                "forecast_days": max(1, min(days, 7))
            }
            w_res = await client.get(weather_url, params=params)
            w_data = w_res.json()

            current = w_data.get("current", {})
            daily = w_data.get("daily", {})

            current_code = current.get("weather_code", 0)
            current_desc = WMO_WEATHER_CODES.get(current_code, "Variabile")
            current_temp = current.get("temperature_2m")
            current_feels = current.get("apparent_temperature")
            current_humidity = current.get("relative_humidity_2m")
            current_wind = current.get("wind_speed_10m")

            forecast_days = []
            dates = daily.get("time", [])
            codes = daily.get("weather_code", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            precip_probs = daily.get("precipitation_probability_max", [])

            for i in range(len(dates)):
                day_label = "Oggi" if i == 0 else ("Domani" if i == 1 else dates[i])
                forecast_days.append({
                    "data": dates[i],
                    "giorno": day_label,
                    "condizione": WMO_WEATHER_CODES.get(codes[i] if i < len(codes) else 0, "Non disponibile"),
                    "temp_max": max_temps[i] if i < len(max_temps) else None,
                    "temp_min": min_temps[i] if i < len(min_temps) else None,
                    "probabilita_pioggia": f"{precip_probs[i]}%" if i < len(precip_probs) and precip_probs[i] is not None else "0%"
                })

            return {
                "success": True,
                "localita": f"{city_name} ({country})",
                "adesso": {
                    "temperatura": f"{current_temp}°C",
                    "percepita": f"{current_feels}°C",
                    "condizione": current_desc,
                    "umidita": f"{current_humidity}%",
                    "vento": f"{current_wind} km/h"
                },
                "previsioni": forecast_days
            }

    except Exception as e:
        logger.error(f"Errore recupero meteo per {location}: {e}")
        return {"success": False, "error": str(e), "message": f"Errore nel recupero meteo per {location}."}
