import os
import pandas as pd
import geopandas as gpd
import json
import pytz
import requests
import json

class istSOSClient:
    WQP_PROCEDURES = ['CHL','TURB','WT']
    TOKEN_URL = "https://istsos.ddns.net/auth/realms/istsos/protocol/openid-connect/token"
    HEADERS = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    SERVICE = "demo"
    OFFERING_NAME = "temporary"
    API_ENDPOINT = f"https://istsos.ddns.net/istsos/wa/istsos/services/{SERVICE}"
    PROCEDURES_LIST = [
        'SATELLITE_CHL_TURB_CO_EAST',
        'SATELLITE_CHL_TURB_CO_NORTH',
        'SATELLITE_CHL_TURB_CO_WEST',
        'SATELLITE_CHL_TURB_LU_EAST',
        'SATELLITE_CHL_TURB_LU_WEST',
        'SATELLITE_CHL_TURB_MA_ALL',
        'SATELLITE_WT_CO_EAST',
        'SATELLITE_WT_CO_NORTH',
        'SATELLITE_WT_CO_WEST',
        'SATELLITE_WT_LU_EAST',
        'SATELLITE_WT_LU_WEST',
        'SATELLITE_WT_MA_ALL',
    ]
    WQP_DEFINITIONS = {
        "Time":{
            "name": "Time",
            "definition": "urn:ogc:def:parameter:x-istsos:1.0:time:iso8601"       
        },
        "CHL":{
            "name": "water-Chl",
            "definition":"urn:ogc:def:parameter:x-istsos:1.0:water:Chl",
            "uom":"mg/m^3"
        },
        "TURB":{
            "name": "water-Turb",
            "definition":"urn:ogc:def:parameter:x-istsos:1.0:water:Turb",
            "uom":"g/m^3" 
        },
        "WT":{
            "name": "water-temperature",
            "definition":"urn:ogc:def:parameter:x-istsos:1.0:water:temperature",
            "uom":"\u00b0C"    
        }    
    }
    
    def __init__(self, TOKEN_URL, HEADERS, API_ENDPOINT, ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            payload = json.load(f)
        self.payload = payload
        self.headers = HEADERS
        self.tokenUrl = TOKEN_URL
        self.apiEndpoint = API_ENDPOINT
        
    def updateBearerToken(self):
        response = requests.post(self.tokenUrl,data=self.payload,headers=self.headers)
        self.authToken = response.json()['access_token']
        self.apiCallBT()
    
    def apiCallBT(self):
        self.requestHeaders = {
            'Content-Type': 'application/json',
            'Authorization' : f'Bearer {self.authToken}'
        }

    def getProcedureIDs(self, PROCEDURES_LIST):
        ASSIGNED_SENSOR_ID = dict()
        for PROCEDURE in  PROCEDURES_LIST:
            url_test = f"{self.apiEndpoint}/procedures/{PROCEDURE}"
            try:
                resp = requests.get(url_test, headers=self.requestHeaders)
                if (resp.status_code==200):
                    try:
                        ASSIGNED_SENSOR_ID[PROCEDURE] = resp.json()['data']['assignedSensorId']
                    except:
                        ASSIGNED_SENSOR_ID[PROCEDURE] = ''
                        print('The procedure {} has not been provided with an ID.'.format(PROCEDURE))
                elif(resp.status_code==401 and resp.json()['message']=='Signature has expired'):
                    self.updateBearerToken()
                    print('Updating authentication token.\n')
                    self.getProcedureIDs(PROCEDURES_LIST)
            except:
                self.updateBearerToken()
                print('Creating authentication token.\n')
                self.getProcedureIDs(PROCEDURES_LIST)
        return ASSIGNED_SENSOR_ID
    
    def getRequestSample(self, PROCEDURE):
        apiRequest = f'/operations/getobservation/offerings/temporary/procedures/{PROCEDURE}/observedproperties/:/eventtime/last'
        response = requests.get(self.apiEndpoint+apiRequest, 
                    headers = self.requestHeaders)
        data = response.json()
        if data['success'] == True:
            print(data['message'])
            data = data['data'][0]
        else:
            print(data['message'])
        
        return data
    
def updateDataRequest(df, dataSample, WQP_DEFINITIONS, WQP_PROCEDURES, PROCEDURE):
    d = dataSample
    wqps = list(set(PROCEDURE.split('_')).intersection(WQP_PROCEDURES))
    DATE_START = pytz.utc.localize(df.date.min()).isoformat().replace('+00:00','Z')
    DATE_END = pytz.utc.localize(df.date.max()).isoformat().replace('+00:00','Z')
    d['samplingTime'] = {
        'beginPosition':DATE_START,
        'endPosition':DATE_END,
    }
    d['procedure'] = f'urn:ogc:def:procedure:x-istsos:1.0:{PROCEDURE}'
    d['observedProperty']['CompositePhenomenon']['dimension'] = str(len(wqps)+1)

    OP_COMPONENT = ["urn:ogc:def:parameter:x-istsos:1.0:time:iso8601"]
    for wqp in wqps: 
        OP_COMPONENT.append(WQP_DEFINITIONS[wqp]['definition'])
    d['observedProperty']['component'] = OP_COMPONENT 
    
    # Data Array
    d['result']['DataArray']['elementCount'] = str(len(wqps)+1)
    
    RES_DA_FIELDS = [WQP_DEFINITIONS['Time']]
    for wqp in wqps: 
        RES_DA_FIELDS.append(WQP_DEFINITIONS[wqp])
    d['result']['DataArray']['field'] = RES_DA_FIELDS
    
    d['result']['DataArray']['values'] = resultsWQPvalues(df, wqps,'_'.join(PROCEDURE.split('_')[-2:]))

    return d
        

def appendStatsFile(df, out_path):
    """
        Export the statistics result to a file (append data if existing)
        df:  Pandas DataFrame exported into the .csv file
        out_path: path to the csv storing the data
    """
    out_file = out_path
    print(out_file)
    if os.path.exists(out_file):
        df.to_csv(out_file,mode='a', header=False)
    else:
        df.to_csv(out_file) 

def getGMLfeature(vector_path, procedure):
    #Retrieve GML feature from GML file polygon type
    with open(os.path.join(vector_path,f'{procedure}.gml')) as f:
        lines = f.read()
    geometry_procedure = lines.split('<ogr:geometryProperty>')[1].split("</ogr:geometryProperty>")[0]
    return geometry_procedure

def resultsWQPvalues(df, WQP_INPUT, BASIN):
    RES_DA_VALUES = []
    wqps = []
    for k in WQP_INPUT:
        if k == 'CHL':
            wqps.append('CHL')
        elif k == 'TURB':
            wqps.append('TSM')
        elif k == 'WT':
            wqps.append('LSWT')     
    df = df.loc[df['typology'].isin(wqps)]
    dates_list = df['date'].unique()
    for d in dates_list:
        temp = [pytz.utc.localize(pd.to_datetime(d)).isoformat().replace('+00:00','Z')]
        for wqp in wqps: 
            try:
                o = df.loc[(df['date']==d)&(df['typology']==wqp)].iloc[0][f'mean_{BASIN}']
                temp.append(o)
            except:
                print('Missing value:', d,':',wqp,':',BASIN)
        if (len(temp)==len(wqps)+1):
            RES_DA_VALUES.append(temp)
    return RES_DA_VALUES

# def buildObservations():
#     print('bruh')
    
# def ingestObservation():
#     print('meme')
    
    