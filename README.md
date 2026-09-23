# PhonePe Pulse Dashboard

Streamlit dashboard built on PhonePe Pulse data, stored in PostgreSQL.

## Setup
1. Install packages: pip install -r requirements.txt
2. Download the data: git clone https://github.com/PhonePe/pulse.git
3. Create a PostgreSQL database named phonepe_db
4. Load the data: python phonepe_master.py  (asks for your DB password)
5. Start the app: streamlit run app/app.py

## Tech
Python, pandas, PostgreSQL, SQLAlchemy, Streamlit, Plotly