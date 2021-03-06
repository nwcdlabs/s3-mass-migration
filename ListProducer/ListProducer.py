#!/usr/bin/python
# -*- coding: utf8 -*-

from pprint import pprint
from utils import *
from s3_utils import *
from sqs_utils import *
from urllib import unquote_plus
import random

# 0. Job
object_key_list= ['totalSizeInBytes', 'totalObjects', 'totalObjectsSub1GB', 'totalObjectsSub5GB', 'totalObjectsSub10GB', 'totalObjectsSub50GB', 'totalObjectsSub100GB', 'totalObjectsSub1TB', 'totalObjectsSub5TB']
# Inventory process


def format_key(key):
    return unquote_plus(key) 
    
def parse_inventory_data_file(session, data_file, job_info=None, profile_name='default'):
    msg_body=[]

    stat={}

    for key in object_key_list:
        stat[key]=0

    with gzip.open(data_file, 'rb') as f:
        for line in f.readlines():
            sections = line.split(',')

            if len(sections) < 7:
                return 1

            src_bucket = sections[0].split('"')[1]
            key = sections[1].split('"')[1]
            size = int(sections[2].split('"')[1])

            item = {
                'Bucket': src_bucket,
                'Key'   : format_key(key),
                'Size'  : size,
                'LastModifiedDate': sections[3].split('"')[1],
                'ETag': sections[4].split('"')[1],
                'StorageClass': sections[5].split('"')[1],
                'IsMultipartUploaded': sections[6].split('"')[1],
                'ReplicationStatus': sections[7].split('"')[1],
                'dst_bucket':job_info['dst']['bucket']
            }

            # Do Stat
            stat['totalSizeInBytes'] += size
            stat['totalObjects'] += 1

            if size > 5*1000*1000*1000:
                pass
                print(">5T...s3://%s/%s"%(src_bucket, key))
            elif size > 1000*1000*1000:
                stat['totalObjectsSub5TB'] += 1
            elif size > 100*1000*1000:
                stat['totalObjectsSub1TB'] += 1
                stat['totalObjectsSub5TB'] += 1
            elif size > 50*1000*1000:
                stat['totalObjectsSub100GB'] += 1
                stat['totalObjectsSub1TB'] += 1
                stat['totalObjectsSub5TB'] += 1
            elif size > 10*1000*1000:
                stat['totalObjectsSub50GB'] += 1
                stat['totalObjectsSub100GB'] += 1
                stat['totalObjectsSub1TB'] += 1
                stat['totalObjectsSub5TB'] += 1
            elif size > 5*1000*1000:
                stat['totalObjectsSub10GB'] += 1
                stat['totalObjectsSub50GB'] += 1
                stat['totalObjectsSub100GB'] += 1
                stat['totalObjectsSub1TB'] += 1
                stat['totalObjectsSub5TB'] += 1
            elif size > 1000*1000:
                stat['totalObjectsSub5GB'] += 1
                stat['totalObjectsSub10GB'] += 1
                stat['totalObjectsSub50GB'] += 1
                stat['totalObjectsSub100GB'] += 1
                stat['totalObjectsSub1TB'] += 1
                stat['totalObjectsSub5TB'] += 1
            else:
                stat['totalObjectsSub1GB'] += 1
                stat['totalObjectsSub5GB'] += 1
                stat['totalObjectsSub10GB'] += 1
                stat['totalObjectsSub50GB'] += 1
                stat['totalObjectsSub100GB'] += 1
                stat['totalObjectsSub1TB'] += 1
                stat['totalObjectsSub5TB'] += 1

            # Bucket, Key, Size, LastModifiedDate, ETag, StorageClass, IsMultipartUploaded, ReplicationStatus
            # "leodatacenter","AWS+SKO+2015/2015+AWS+Sales+Kickoff+Agenda.pdf","360461","2015-08-29T06:56:01.000Z","eef4ce1bc8503f5ee6c98553ccb9f496","STANDARD","false",""

            #print src_bucket,key,dst_bucket
            #print src_bucket,key

            #msg_body.append({'src_bucket':src_bucket, 'key':key, 'dst_bucket':job_info['dst_bucket']})
            msg_body.append(item)

            if len(msg_body) == job_info['queue']['message_body_max_num']:
                qurl='%s-%03d'%(job_info['queue']['url_prefix'], random.randint(1, job_info['queue']['num']))
                session.send_msg_to_sqs(qurl, msg_body)
                msg_body=[]

    if len(msg_body) > 0:
        qurl='%s-%03d'%(job_info['queue']['url_prefix'], random.randint(1, job_info['queue']['num']))
        session.send_msg_to_sqs(qurl, msg_body)

    pprint(stat)

    return stat 

def downlad_bucket_manifest(session, dst_bucket, dst_obj):
    ''' test FIXME '''
    # leo-bjs-inventory-bucket', 'leodatacenter/leodatacenter/2017-12-25T08-00Z/
    data = session.load_json_from_s3_object(dst_bucket, dst_obj)
    pprint(data)
    return data

def main():
    # 0. Initial
    # load job_info
    ## TODO: Will load job.json based on para
    job_info = load_json_from_file('../job.json')

    pprint(job_info)

    src_profile = s3Class(profile_name=job_info['src']['profile'])
    dst_profile = s3Class(profile_name=job_info['dst']['profile'])
    sqs_profile = sqsClass(profile_name=job_info['dst']['profile'])

    # 1. Get Source information
    manifest = downlad_bucket_manifest(src_profile, job_info['src']['inventory_bucket'], job_info['src']['inventory_manifest_dir']+'manifest.json')

    manifest['statistics'] = {}
    for key in object_key_list:
        manifest['statistics'][key]=0

    #pprint(manifest)
    if 'files' in manifest:
        for item in manifest['files']:
            pprint(item)
            download_filename = src_profile.download_s3_object_from_inventory(job_info['src']['inventory_bucket'], item)

            stat = parse_inventory_data_file(sqs_profile, download_filename, job_info)
            #print(stat)

            for key in object_key_list:
                manifest['statistics'][key] += stat[key]

    print("============")
    manifest['job_info'] = job_info

    pprint(manifest)

    #save back manifest 

    dst_profile.save_json_to_s3_object(manifest, job_info['job_bucket'], '{}/job_stat.json'.format(job_info['job_dir']))

    #data = dst_profile.load_json_from_s3_object(job_info['job_bucket'], '{}/job.json'.format(job_info['job_dir']))
    #pprint(data)

    print("=== Job description is at s3://{}/{}".format(job_info['job_bucket'], '{}/job_stat.json'.format(job_info['job_dir'])))

    sys.exit()

if __name__ == '__main__':
    main()
