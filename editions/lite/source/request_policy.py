"""Validate chat structure before changing a loaded model; local UI response policy."""
import json,math

def chat_payload(raw):
 def invalid_constant(value):raise ValueError('Non-finite JSON number.')
 try:value=json.loads(raw,parse_constant=invalid_constant)
 except (ValueError,TypeError,RecursionError) as ex:raise ValueError('Chat request must contain valid JSON.') from ex
 if not isinstance(value,dict):raise ValueError('Chat request must be a JSON object.')
 messages=value.get('messages')
 if not isinstance(messages,list) or not 1<=len(messages)<=500:raise ValueError('Provide one to 500 chat messages.')
 images=0
 for message in messages:
  if not isinstance(message,dict) or message.get('role') not in ('system','user','assistant','tool'):raise ValueError('Invalid chat message role.')
  content=message.get('content')
  if isinstance(content,str):continue
  if not isinstance(content,list) or not content:raise ValueError('Chat content must be text or supported attachments.')
  for part in content:
   if not isinstance(part,dict):raise ValueError('Invalid chat attachment.')
   if part.get('type')=='text' and isinstance(part.get('text'),str):continue
   if part.get('type')=='image_url' and isinstance(part.get('image_url'),dict):
    url=part['image_url'].get('url')
    if not isinstance(url,str) or not url.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,','data:image/bmp;base64,')):raise ValueError('Use attached local image data, not a remote image URL.')
    images+=1;continue
   raise ValueError('Unsupported chat attachment.')
  if not any(part.get('type')=='image_url' for part in content):message['content']='\n'.join(part['text'] for part in content)
 if images>4:raise ValueError('Use at most four attached images.')
 if 'stream' in value and type(value['stream']) is not bool:raise ValueError('stream must be true or false.')
 if 'max_tokens' in value and (type(value['max_tokens']) is not int or value['max_tokens']<1):raise ValueError('max_tokens must be a positive integer.')
 if 'temperature' in value and (type(value['temperature']) not in (float,int) or not math.isfinite(value['temperature']) or value['temperature']<0):raise ValueError('temperature must be a finite nonnegative number.')
 if 'response_format' in value and not isinstance(value['response_format'],dict):raise ValueError('response_format must be an object.')
 return value

def page_headers():
 return {'Content-Security-Policy':"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'",'X-Frame-Options':'DENY','X-Content-Type-Options':'nosniff','Cache-Control':'no-store'}
