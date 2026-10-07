import streamlit as st

navigation = st.navigation([
    st.Page("pages/Process_Invoices.py", title="Process invoices", default=True),
    st.Page("pages/Dashboard.py", title="Dashboard"),
    st.Page("pages/Invoice_History.py", title="Invoice history"),
])
navigation.run()
