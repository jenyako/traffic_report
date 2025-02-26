import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import json
from io import StringIO

def fetch_data(file, tables_list, evosession, startDate, endDate, settings_list):
    df_casinos = pd.read_csv(file)

    bo_headers =  {
        "Cookie": f"EVOSESSIONID={evosession}"
    }

    casinos = df_casinos['casino_id'].to_list()
    df_assigned = pd.DataFrame(columns=(['casino_id', 'table_id', 'game_type']+settings_list+['number_of_virtual_tables', 'virtual_tables_settings']))
    
    with st.status(label="Reading Casinos List", state="running") as status:
        status.update(label="Receiving Tables Assignment Status", state="running")

    for casino_id in casinos:
        status.update(label=f"Receiving Tables Assignment Status for {casino_id}", state="running")
        url = f'https://livecasino.evolutiongaming.com/api/admin/casino/{casino_id}/tables'
        response = requests.get(url, headers=bo_headers)
        if response.status_code != 200:
            print(f"Error: Failed to fetch data for casino_id {casino_id}. Status code: {response.status_code}")
            continue
        data = response.json()
        
        

        for table_id in tables_list:
            for i in data:
                if i['id'] == table_id:
                    url = f'https://livecasino.evolutiongaming.com/api/admin/casino/{casino_id}/tables/{table_id}'
                    response = requests.get(url, headers=bo_headers)
                    data_table = response.json()


                    new_row = {'casino_id': casino_id, 'table_id': table_id, 'game_type': i['gameType'], 'number_of_virtual_tables': len(i['virtualTables'])}
                    
                    for setting in settings_list:
                        if setting in data_table['config']:
                            new_row[setting] = data_table['config'][setting]
                    
                    if len(i['virtualTables'])>0:
                        v_tables_settings = ''
                        for j in i['virtualTables']:
                            v_tables_settings += j['id']+':\n'
                            for setting in settings_list:
                                if setting in j['config']:
                                    value = j['config'][setting]
                                    if len(value)>0:
                                        v_tables_settings += f'{setting}={value}'+'\n'
                        new_row['virtual_tables_settings'] = v_tables_settings.strip().strip(':')
                        
                    df_assigned = pd.concat([df_assigned, pd.DataFrame([new_row])], ignore_index=True)

                            
                    

    df_assigned['rounds_count'] = ''
    df_assigned['notes'] = ''
    
    status.update(label="Analyzing Tables Traffic", state="running")

    for casino_id in casinos:
        status.update(label=f"Analyzing Tables Traffic for {casino_id}", state="running")
        token = df_casinos.loc[df_casinos['casino_id'] == casino_id,'gameHistoryApi_token'].item()
        basic_auth = HTTPBasicAuth(casino_id, token)
        casino_tables = df_assigned[df_assigned['casino_id'] == casino_id]['table_id'].tolist()

        for table_id in casino_tables:
            game_type = df_assigned[df_assigned['table_id'] == table_id]['game_type'].iloc[0]
            url = f'https://alive.evo-games.com/api/gamehistory/v1/casino/daily-report?startDate={startDate}&endDate={endDate}&gameType={game_type}'
            response = requests.get(url, auth=basic_auth, timeout=10)

            if response.status_code != 200:
                df_assigned.loc[(df_assigned['casino_id'] == casino_id) & (df_assigned['table_id'] == table_id), 'notes'] = f"Error: Failed to fetch data. Status code: {response.status_code}, Response content: {response.content}"
            else:
                rounds_count = 0
                data = response.json()
                if 'data' in data:
                    for item in data['data']:
                        table_data = item.get("table", {})
                        table_reported = table_data.get("id", "N/A")
                        if table_reported == table_id:
                            rounds_count += item.get("roundCount", "N/A")
                else:
                    df_assigned.loc[(df_assigned['casino_id'] == casino_id) & (df_assigned['table_id'] == table_id), 'notes'] = "The key 'data' is not present in the main dictionary."
                df_assigned.loc[(df_assigned['casino_id'] == casino_id) & (df_assigned['table_id'] == table_id), 'rounds_count'] = rounds_count
    status.update(label="Analysis Done", state="complete")
    return df_assigned

def main():
    """
    Main function to run the Streamlit app.
    """
    st.title("Traffic Review")
    st.sidebar.header("Configuration")

    # Input Parameters
    file = st.sidebar.file_uploader("Upload Tthe List of Casinos", type=['csv'])
    tables_list_input = st.sidebar.text_input("Tables List (comma-separated)", "RaceTrack0000001, FreeBet000000001")
    tables_list = [item.strip() for item in tables_list_input.split(',')] if tables_list_input else []
    evosession = st.sidebar.text_input("EVOSESSIONID", "")
    st.sidebar.write("Maximum reporting period is 30 days")
    start_date = st.sidebar.date_input("Start Date", value="today")
    end_date = st.sidebar.date_input("End Date", value="today")
    settings_list_input = st.sidebar.text_input("Settings List (comma-separated)", "display, siteAssignedTable, siteBlockedTable")
    settings_list = [item.strip() for item in settings_list_input.split(',')] if settings_list_input else []


    start_date = start_date.strftime('%Y-%m-%d')
    end_date = end_date.strftime('%Y-%m-%d')

    if st.sidebar.button("Generate Report"):
        if file is not None:
            try:
                df = fetch_data(file, tables_list, evosession, start_date, end_date, settings_list)
                st.dataframe(df)
                

                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name=f'traffic_report_{start_date}-{end_date}.csv',
                    mime='text/csv',
                )
            except Exception as e:
                st.error(f"An error occurred: {e}")
        else:
            st.error("Please upload the casinos_list.csv file.")

if __name__ == "__main__":
    main()