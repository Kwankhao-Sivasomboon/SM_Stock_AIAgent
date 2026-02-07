# AIAgent LineStock - AI-Powered Personal Investment Assistant

A smart LINE Chatbot functioning as a personal financial analyst. It uses **Google Gemini 2.0 Flash** with **Finnhub, Settrade, and Twelve Data APIs** to analyze stock market data, technical indicators, and news in real-time, providing personalized investment recommendations based on user profiles.

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
*   **AI/LLM**: Google Gemini 2.0 Flash (`google-genai` SDK)
*   **Data Sources**:
    *   **Finnhub**: US/Global Stock News & Fundamental Data
    *   **Twelve Data**: Real-time US Price & Technical Indicators
    *   **Settrade Open API**: Thai Stock Data (Direct Access)
*   **Database**: PostgreSQL (Google Cloud SQL)
*   **Task Scheduling**: APScheduler (Background Worker)
*   **Platform**: LINE Messaging API (Webhook & Push API)
*   **Deployment**: Docker, Google Cloud Run

## Architecture

The system follows a modern **Event-Driven Analysis** flow with robust error handling:

1.  **Ingestion**: LINE Webhook triggers the Flask server using a Deduplication logic to ignore redelivery events.
2.  **Ack**: Server replies immediately (200 OK) or sends a waiting message to prevent timeout loop.
3.  **Smart Caching**: 
    *   **Global Stocks**: Fundamental data (P/E, Market Cap) is cached in PostgreSQL to reduce API calls and latency.
    *   **Thai Stocks**: Direct real-time fetch via Settrade API (No caching needed).
4.  **Sequential Processing**: The Background Worker processes stocks sequentially with enforced delays to respect Third-Party API Rate Limits (e.g., Twelve Data).
5.  **Delivery**: Analyzed results (Signal, Reason, Chart, News) are pushed back to the user via Flex Messages.

## Challenges & Solutions

*   **Challenge**: LINE Webhook Redelivery causing duplicate messages.
    *   **Solution**: Implemented **Request Deduplication** by checking the `isRedelivery` flag in the delivery context, ensuring only unique events are processed.
*   **Challenge**: API Rate Limits and Missing Data (e.g., ETF P/E).
    *   **Solution**:
        *   **Smart Fallback**: If primary data is missing (0 or Null), the system displays "N/A" instead of misleading zeros.
        *   **Caching Strategy**: A daily maintenance job prunes old cache entries at 03:00 AM (Market Close) to ensure fresh data for the next trading day.
        *   **Delays**: Added precise sleep intervals between requests to stay within free tier limits.
*   **Challenge**: Slow External APIs (Finnhub) causing timeouts.
    *   **Solution**: Reduced API timeouts to 3 seconds and implemented a **Fail-Fast** mechanism to prioritize system responsiveness over complete data in worst-case scenarios.

## License
This project is for educational and portfolio purposes.
