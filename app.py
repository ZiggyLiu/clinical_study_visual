import requests
import pandas as pd
import time
import streamlit as st
import numpy as np
import plotly.express as px

# Sidebar or main page input
disease_input = st.text_input("Enter disease name to fetch trials", value="ALS")


def fetch_trials(condition="ALS", max_studies=5000, page_size=1000, delay=0.2):
    """
    Fetch studies from ClinicalTrials.gov API with pagination.
    
    Args:
        condition (str): search term
        max_studies (int): maximum number of studies to fetch
        page_size (int): number of studies per request (API max ≈ 1000)
        delay (float): delay (in seconds) between requests (to avoid rate-limiting)
    """
    url = "https://clinicaltrials.gov/api/v2/studies"
    all_records = []
    next_page_token = None

    while len(all_records) < max_studies:
        params = {
            "query.term": condition,
            "pageSize": min(page_size, max_studies - len(all_records)),
            "format": "json"
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        response = requests.get(url, params=params)
        print("Status:", response.status_code)

        if response.status_code != 200:
            raise Exception(f"API request failed: {response.status_code}\n{response.text[:500]}")

        data = response.json()
        studies = data.get("studies", [])
        next_page_token = data.get("nextPageToken")

        for s in studies:
            protocol = s.get("protocolSection", {})
            id_info = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
            design_module = protocol.get("designModule", {})
            enrollment_info = design_module.get("enrollmentInfo", {})

            all_records.append({
                "NCT_ID": id_info.get("nctId"),
                "Title": id_info.get("briefTitle"),
                "Status": status_module.get("overallStatus"),
                "Phase": design_module.get("phaseList", {}).get("phases", [None])[0],
                "Sponsor": sponsor_module.get("leadSponsor", {}).get("name"),
                "Enrollment": enrollment_info.get("value"),
                "StartDate": status_module.get("startDateStruct", {}).get("date"),
                "CompletionDate": status_module.get("completionDateStruct", {}).get("date"),
            })

        # Stop if no more pages
        if not next_page_token or len(studies) == 0:
            break

        # Rate-limit to avoid hammering the API
        time.sleep(delay)

    return pd.DataFrame(all_records[:max_studies])




if disease_input:
    with st.spinner(f"Fetching trials for '{disease_input}'..."):
        df = fetch_trials(disease_input, max_studies=1000)

@st.cache_data(ttl=3600)
def fetch_trials_cached(condition, max_studies=1000):
    return fetch_trials(condition, max_studies=max_studies)
df = fetch_trials_cached(disease_input, max_studies=1000)

#disease = st.sidebar.multiselect("Disease", options=df["Disease"].unique(), #default=df["Title"].unique())
#phase = st.sidebar.multiselect("Phase", options=df["Phase"].unique(), default=df["Phase"].unique())
status = st.sidebar.multiselect("Status", options=df["Status"].unique(), default=df["Status"].unique())
sponsor = st.sidebar.multiselect("Sponsor", options=df["Sponsor"].unique(), default=df["Sponsor"].unique())

# Make sure StartDate and CompletionDate are proper datetimes
df["StartDate"] = pd.to_datetime(df["StartDate"], errors="coerce")
df["CompletionDate"] = pd.to_datetime(df["CompletionDate"], errors="coerce")

# Calculate duration in months
df["Duration_months"] = (
    (df["CompletionDate"] - df["StartDate"]).dt.days / 30.44
)

# --- Apply filters ---
filtered = df[
    (df["Sponsor"].isin(sponsor)) &
    (df["Status"].isin(status))
]

# --- Key Metrics ---
st.title("Rare Disease Clinical Trial Landscape")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Trials", len(filtered))
col2.metric("Active Sponsors", filtered["Sponsor"].nunique())

median_enrollment = filtered["Enrollment"].median()

if pd.isna(median_enrollment):
    col3.metric("Median Enrollment", "-")
else:
    col3.metric("Median Enrollment", int(median_enrollment))


median_duration = filtered["Duration_months"].median()
if pd.isna(median_duration):
    median_duration = 0  # or whatever default makes sense
col4.metric("Median Duration (months)", median_duration)


# --- Charts ---
fig1 = px.bar(filtered["Status"].value_counts(), title="Trials by Status")
st.plotly_chart(fig1)

fig2 = px.bar(filtered["Sponsor"].value_counts().head(5), orientation="h", title="Top Sponsors")
st.plotly_chart(fig2)

fig3 = px.histogram(filtered, x="Enrollment", nbins=10, title="Enrollment Distribution")
st.plotly_chart(fig3)

# --- Data Table ---
st.subheader("Filtered Trials")
st.dataframe(filtered)