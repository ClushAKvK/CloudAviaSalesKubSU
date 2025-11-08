import React, { useState, useEffect } from "react";
import { getFlights, buyTicket } from "./api";
import "./App.css";

function App() {
  const [flights, setFlights] = useState([]);
  const [selectedFlight, setSelectedFlight] = useState(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    getFlights().then((data) => setFlights(data));
  }, []);

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://smartcaptcha.yandexcloud.net/captcha.js";
    script.async = true;
    script.onload = () => {
      const container = document.getElementById("captcha-container");
      if (window.smartCaptcha && container) {
        window.smartCaptcha.render({
          sitekey: "ysc1_KwOg43ujxx1eWxFlJDRfzPMiaKkgqYFpC5MzEGd02ae283d2",
          containerId: "captcha-container",
          invisible: false,
        });
      }
    };
    document.body.appendChild(script);
  }, []);

  const handleBuy = async () => {
    if (!selectedFlight) {
      setMessage("Выберите рейс");
      return;
    }

    const token = window.smartCaptcha?.getResponse();
    if (!token) {
      setMessage("Пройдите капчу");
      return;
    }

    setMessage("Отправка покупки...");
    const resp = await buyTicket({
      flight_id: selectedFlight,
      passenger_name: name,
      email,
      captcha_token: token,
    });

    if (resp.ticket_url) {
      setMessage(
        <>
          ✅ Билет готов:{" "}
          <a href={resp.ticket_url} target="_blank" rel="noopener noreferrer">
            Открыть билет
          </a>
        </>
      );
    } else {
      setMessage(`❌ Ошибка: ${resp.error || JSON.stringify(resp)}`);
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>Flight Booking Lab</h1>
      </header>

      <section className="flights-section">
        <h2>Доступные рейсы</h2>
        <div className="flights-grid">
          {flights.map((f) => (
            <div
              key={f.id}
              className={`flight-card ${
                selectedFlight === f.id ? "selected" : ""
              }`}
              onClick={() => setSelectedFlight(f.id)}
            >
              <div className="flight-number">✈️ {f.number}</div>
              <div className="flight-route">
                {f.departure} → {f.arrival}
              </div>
              <div className="flight-price">{f.price} ₽</div>
              <button
                className="select-btn"
                onClick={() => setSelectedFlight(f.id)}
              >
                Выбрать
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="buy-section">
        <h2>Покупка билета</h2>
        <div className="buy-form">
          <div className="form-row">
            <label>Выбранный рейс:</label>
            <span>{selectedFlight || "—"}</span>
          </div>
          <input
            type="text"
            placeholder="ФИО"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            type="email"
            placeholder="E-mail"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <div
            id="captcha-container"
            className="smart-captcha"
            data-sitekey="ysc1_KwOg43ujxx1eWxFlJDRfzPMiaKkgqYFpC5MzEGd02ae283d2"
          ></div>
          <button className="buy-btn" onClick={handleBuy}>
            Купить билет
          </button>
        </div>
        <div className="message">{message}</div>
      </section>

      <footer className="footer">© 2025 Flight Booking Lab</footer>
    </div>
  );
}

export default App;
