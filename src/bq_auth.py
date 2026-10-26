"""Log in to Google BigQuery with your own Google account.

A browser window opens. Sign in and click "Allow".
The login token is saved in your user folder (not in this repo),
so you only need to do this once.
"""
import pydata_google_auth
from google.cloud import bigquery

SCOPES = ["https://www.googleapis.com/auth/bigquery"]


def get_credentials():
    return pydata_google_auth.get_user_credentials(SCOPES, use_local_webserver=True)


if __name__ == "__main__":
    creds = get_credentials()
    client = bigquery.Client(credentials=creds, project="bigquery-public-data")
    projects = list(client.list_projects())
    print("Login OK. Your projects:", [p.project_id for p in projects])
