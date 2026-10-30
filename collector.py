import urllib.request,urllib.parse,hashlib,json
from datetime import datetime,timezone,timedelta

def fetch(path,action):
 d=dict(action=action,routeName='701X',dir='0',lang='zh-tw',device='web')
 raw='&'.join(f'{k}={v}' for k,v in d.items())
 h=hashlib.md5(raw.encode()).hexdigest(); t=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d%H%M')
 token=h[:4]+t[:4]+h[4:12]+t[4:8]+h[12:24]+t[8:]+h[24:]
 req=urllib.request.Request('https://bis.dsat.gov.mo:37812/macauweb/'+path,data=urllib.parse.urlencode(d).encode(),headers={'token':token,'User-Agent':'Mozilla/5.0'})
 return json.load(urllib.request.urlopen(req,timeout=15))
if __name__=='__main__':
 for path,action,name in [('getRouteData.html','sd','route.json'),('routestation/bus','dy','buses.json')]:
  data=fetch(path,action)
  open(name,'w',encoding='utf-8').write(json.dumps(data,ensure_ascii=False,indent=2))
  print(name,json.dumps(data,ensure_ascii=True)[:16000])
