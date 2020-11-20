import http.client, urllib
import boto3
import pandas as pd
import os


def send_message(msg, sound = 'pushover'):
    conn = http.client.HTTPSConnection("api.pushover.net:443")
    conn.request("POST", "/1/messages.json",
      urllib.parse.urlencode({
        "token": os.environ.get('PUSHOVER_APPTOKEN'), 
        "user": os.environ.get('PUSHOVER_USERKEY'),
        "message": msg,
        "sound" : sound
      }), { "Content-type": "application/x-www-form-urlencoded" })
    conn.getresponse()
    
# verify recency of bucket
def get_all_s3_objects(s3, **base_kwargs):
    continuation_token = None
    while True:
        list_kwargs = dict(MaxKeys=1000, **base_kwargs)
        if continuation_token:
            list_kwargs['ContinuationToken'] = continuation_token
        response = s3.list_objects_v2(**list_kwargs)
        yield from response.get('Contents', [])
        if not response.get('IsTruncated'):  # At the end of the list?
            break
        continuation_token = response.get('NextContinuationToken')
        
# verifies whether Netflix DC is running
def check_s3(bucket='uvt-netflix', directory='raw/csv', min_filesize=100000,
             min_files = 3, max_recency=0):
    s3_client = boto3.client('s3')
    
    response_contents = []
    for o in get_all_s3_objects(s3_client, Bucket=bucket, Prefix=directory):
        response_contents.append(o)
    
    from datetime import datetime
    
    df = pd.DataFrame(response_contents)  
    df=df.sort_values(by=['LastModified'], ascending=False)
    df = df.set_index(['LastModified'])
    df['now'] = pd.Timestamp(datetime.now())
    
    df['LastModifiedNoTz'] = pd.to_datetime(df.index, format='%Y-%m-%d %H:%M:%S')
    df['LastModifiedNoTz']= df['LastModifiedNoTz'].dt.tz_localize(None)
   
    df['timediff'] = (df['now'].dt.date-df['LastModifiedNoTz'].dt.date).dt.days
    
    result = df.query('Size>'+str(min_filesize)+'&timediff<='+str(max_recency)) #1kb
    
    return(result.shape[0]>=min_files)

def statusmsg(truefalse):
    if (truefalse==True): return('healthy')
    if (truefalse==False): return('ERROR!')
        
# verifies whether Netflix DC is running
def health_netflix():
    return(check_s3(bucket='uvt-netflix', directory='raw/csv',
             min_filesize=100000, min_files=3))

def health_worldbrowser():
    return(check_s3(bucket='uvt-streaming-data', directory='everynoise/worldbrowser/',
             min_filesize=4000000, min_files=2))

def health_newreleases():
    return(check_s3(bucket='uvt-streaming-data', directory='everynoise/new-releases/',
             min_filesize=200*1E6, min_files=1, max_recency=7)) # larger than 200 MB

def monitoring_message():
    health1=health_netflix()
    health2=health_worldbrowser()
    health3=health_newreleases()
    msg = []
    msg.append('Monitoring message')
    msg.append('Netflix: ' + statusmsg(health1))
    msg.append('Everynoise worldbrowser: ' + statusmsg(health2))
    msg.append('Everynoise new releases: ' + statusmsg(health3))
    sound = 'magic'
    if (health1==False|health2==False|health3==False): sound = 'siren'
    send_message('\n'.join(msg), sound=sound)

monitoring_message()
