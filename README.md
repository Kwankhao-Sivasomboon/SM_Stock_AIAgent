# AIAgent LineStock - AI-Powered Personal Investment Assistant

A smart LINE Chatbot functioning as a personal financial analyst. It uses **Google Gemini 3 (Flash)** to analyze stock market data, technical indicators, and news in real-time, providing personalized investment recommendations based on user profiles.

![Banner/Demo Image Placeholder](https://via.placeholder.com/800x400?text=AI+Stock+Agent+Demo)

## Key Features

*   **AI-Driven Analysis**: Utilizes **Gemini 3 Flash** to interpret complex financial data into simple advice ("BUY", "SELL", "WAIT", "HOLD").
*   **Personalized Strategy**: Users can define their investment style (Value, Growth, DCA), Goal (Short/Long term), and Risk Tolerance.
*   **Technical & Fundamental**: Automatically calculates RSI, SMA(50), and fetches P/E, Div Yield, and recent news for comprehensive analysis.
*   **High Performance Architecture**: Implements **Fire-and-Forget Threading** to handle LINE Webhooks immediately while processing heavy AI tasks in the background (Non-blocking I/O).
*   **Automated Scheduler**: Hourly background worker checks user watchlists and pushes alerts based on market conditions.
*   **Rich UX/UI**: Uses LINE Flex Messages with dynamic color coding and sparkline charts for distinct visualization.

## Tech Stack

*   **Core**: Python 3.10, Flask
*   **AI/LLM**: Google Gemini API (`google-genai` SDK)
*   **Data**: `yfinance` (Yahoo Finance API), Pandas
*   **Database**: SQLite (SQLAlchemy ORM)
*   **Task Scheduling**: APScheduler (Background Worker)
*   **Concurrency**: Python `threading` & `concurrent.futures`
*   **Platform**: LINE Messaging API (Webhook & Push API)
*   **Deployment**: Docker, Google Cloud Run (Ready)

## Architecture

The system follows a modern **Event-Driven Analysis** flow:
1.  **Ingestion**: LINE Webhook triggers the Flask server.
2.  **Ack**: Server replies immediately (200 OK) to prevent timeout/retries.
3.  **Background Processing**: A detached thread fetches data and calls Gemini AI.
4.  **Delivery**: Results are pushed back to the user asynchronously.

## Screenshots

| Watchlist Carousel | AI Analysis Report | Settings Menu |
|:------------------:|:------------------:|:-------------:|
| ![Watchlist](https://via.placeholder.com/200x400?text=Watchlist) | ![Analysis](https://via.placeholder.com/200x400?text=Analysis) | ![Settings](https://via.placeholder.com/200x400?text=Settings) |

## Challenges & Solutions

*   **Challenge**: LINE Webhook timeout (30s) when waiting for AI analysis.
    *   **Solution**: Implemented a **Fire-and-Forget** threading mechanism to acknowledge the request instantly and process the AI workload asynchronously, preventing duplicate webhook triggers.
*   **Challenge**: Token limits and API costs.
    *   **Solution**: Added **Rate Limiting (Cooldown)** logic to prevent spamming and optimized prompt engineering to reduce token usage per request.

## License
This project is for educational and portfolio purposes.
