"""Read-only CI reconciliation of default-branch code-scanning alerts. Never prints credentials or code."""
import json,os,re,urllib.request
from pathlib import Path

def main():
 repo=os.environ['GITHUB_REPOSITORY']
 if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Invalid repository')
 token=os.environ.get('GH_TOKEN','')
 if not token:print('Code-scanning inventory unavailable: CI token was not supplied.');return
 rows=[]
 for page in range(1,11):
  url=f'https://api.github.com/repos/{repo}/code-scanning/alerts?state=open&per_page=100&page={page}'
  req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'YOEAI-security-reconciliation'})
  try:
   with urllib.request.urlopen(req,timeout=30) as response:data=json.load(response)
  except urllib.error.HTTPError as error:
   print('Code-scanning inventory unavailable: HTTP '+str(error.code));return
  for item in data:
   location=item.get('most_recent_instance',{}).get('location',{})
   rows.append({'number':item['number'],'rule':item['rule']['id'],'severity':item['rule'].get('security_severity_level'),'path':location.get('path'),'line':location.get('start_line')})
  if len(data)<100:break
 result={'openAlerts':len(rows),'alerts':rows,'scope':'Read-only default repository code-scanning inventory; no dismissal or security-setting changes.'}
 Path('security-status.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print('YOEAI_SECURITY_INVENTORY '+json.dumps(result))
if __name__=='__main__':main()
