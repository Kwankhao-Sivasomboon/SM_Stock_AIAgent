# AIAgent LineStock - AI-Powered Personal Investment Assistant

A smart LINE Chatbot functioning as a personal financial analyst. It uses **Google Gemini 2.5 (Flash)** with **Finnhub API** to analyze stock market data, technical indicators, and news in real-time, providing personalized investment recommendations based on user profiles.

## UX/UI
| Add Stock | Scheduler | Watchlist Carousel |
|:---------:|:---------:|:------------------:|
| <img width="371" height="222" alt="Add" src="https://github.com/user-attachments/assets/ee16bde5-bf96-4590-bd08-85b7ea32047b" /> | <img width="377" height="370" alt="Scheduler" src="https://github.com/user-attachments/assets/41659e15-be0d-4a5a-9dfb-2bbe8d044238" /> | <img width="751" height="340" alt="WatchList" src="https://github.com/user-attachments/assets/4c8dc80b-0388-4cac-9664-b1b174e363a7" /> |

|Settings Menu |
|:------------:|
| <img width="1529" height="588" alt="MainSetting" src="https://github.com/user-attachments/assets/922fb671-fb05-4ca9-b4f0-081b455c808f" /> |

| AI Analysis Report |
|:------------------:|
| <img width="1531" height="722" alt="Report" src="https://github.com/user-attachments/assets/2673091d-c41f-4f9d-934a-d8f198ae4cbf" /> |

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

## Challenges & Solutions

*   **Challenge**: LINE Webhook timeout (30s) when waiting for AI analysis.
    *   **Solution**: Implemented a **Fire-and-Forget** threading mechanism to acknowledge the request instantly and process the AI workload asynchronously, preventing duplicate webhook triggers.
*   **Challenge**: Token limits and API costs.
    *   **Solution**: Added **Rate Limiting (Cooldown)** logic to prevent spamming and optimized prompt engineering to reduce token usage per request.

## License
This project is for educational and portfolio purposes.
