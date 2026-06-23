#!/bin/bash
cd /home/ubuntu/wechat-publisher
export WECHAT_APPID=wx8317fbdafcbcd670
export WECHAT_SECRET=f884a545f472f7b5500022594e543fdd
export SITE_URL=https://spacenetx.com
export PATH=/home/ubuntu/venv/bin:$PATH
python3 publish_ds.py >> /home/ubuntu/wechat-publisher/run.log 2>&1
