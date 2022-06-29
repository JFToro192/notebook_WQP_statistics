import os
import csv
from datetime import datetime
import numpy as np
import pandas as pd
import rasterio
from rasterstats import zonal_stats, point_query

class wqp:
    
    # Extract the metadata of the datasets    
    def __init__(self, path):
        # Sentinel-3 
        date_format = "%Y%m%dT%H%M%S" 
        
        temp_path = path.split('\\')
        name = temp_path[-1].split('.')[0]
        self.path = path
        self.name = name
        self.sensor = name.split('_')[0]
        self.typology = name.split('_')[1]
        self.crs = name.split('_')[2]
        if (self.sensor in ['S3A','S3B']):
            self.date = datetime.strptime(name.split('_')[3], date_format)
        
    
    # Read the datasets using rasterio
    def readWQP(self):
        self.image = rasterio.open(self.path)
        
    # Close the dataset using rasterio
    def closeWQP(self):
        self.image.close()
        
    def writeWQP(self, out_path, array):
        # Register GDAL format drivers and configuration options with a
        # context manager.
        with rasterio.Env():

            # Write an array as a raster band to a new 8-bit file. For
            # the new file's profile, we start with the profile of the source
            profile = self.image.profile

            # And then change the band count to 1, set the
            # dtype to uint8, and specify LZW compression.
            profile.update(
                dtype=rasterio.uint8,
                count=1,
                compress='lzw')

            with rasterio.open(os.path.join(out_path,self.name+'.tif'), 'w', **profile) as dst:
                dst.write(array.astype(rasterio.uint8), 1)
    
    # Compute the zonal statistics for a reference raster and polygon
    def computeStatistics(self, vectorData, nameField, stats, nodata):
        # Default stats returned by the method
        # Use the stats documentation provided for rasterstats
        zs_temp = zonal_stats(vectorData, self.path, stats=stats, nodata=nodata)
        
        # Organize the data according to the feature
        zs = dict()
        j = 0
        for d in zs_temp:
            zs[vectorData.loc[j]['Nome']] = d
            j += 1
            
        self.stats = zs
        

    # Extract point data from the reference product for single band raster
    def extractSamplePoints(self, vectorData):
        obs = []
        
        for point in vectorData['geometry']:
          
            x = point.xy[0][0]
            y = point.xy[1][0]
            row, col = self.image.index(x,y)
            
            o = [x,y,row,col,self.image.read(1)[row,col]]
            
            obs.append(o)
        
        df = pd.DataFrame(obs, columns = ['x','y','row','col',self.typology])
        
        self.samplePoint = df
        
    def organizeWQPEstimates(d_stats):
        # Organize the WQP descriptive statistics in an structure suitable to be exported as a dataframe
        d = dict()
        for key_feature in d_stats:
            for key_stat in d_stats[key_feature]:
                d['{}_{}'.format(key_stat,key_feature)] = d_stats[key_feature][key_stat]
        return d
    
    def exportWQPFormatEstimates(src):
        d = wqp.organizeWQPEstimates(src.stats)
        stats_keys = list(d.keys())
        
        #TODO: exception on null value for the samplePoints
        d['name'] = src.name
        d['path'] = src.path
        d['sensor'] = src.sensor
        d['typology'] = src.typology
        d['crs'] = src.crs
        d['date'] = src.date
        
        cols = ['name','path', 'sensor', 'typology', 'crs', 'date']
        con = np.concatenate((cols,stats_keys))

        df = pd.DataFrame([d])
        
        df = df.reindex(columns = con)
        
        return df
        
        

            
   