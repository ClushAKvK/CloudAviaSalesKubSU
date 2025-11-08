const API_BASE = "https://d5dk7mk1tt8shgpqk2ll.9bgyfspn.apigw.yandexcloud.net"; // позже замените, когда получите endpoint

export async function getFlights() {
  const r = await fetch(`${API_BASE}/flights`);
  return r.json();
}

export async function buyTicket({flight_id, passenger_name, email, captcha_token}) {
  const r = await fetch(`${API_BASE}/buy`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({flight_id, passenger_name, email, captcha_token})
  });
  return r.json();
}
