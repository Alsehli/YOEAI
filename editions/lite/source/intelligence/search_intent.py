"""Conservative fallback only when structured local tool planning fails."""
import re

def requires_sources(question):
 text=question.casefold()
 if re.search(r'^(?:summari[sz]e|rewrite|translate|لخص|ترجم)\b',text):return False
 return bool(re.search(r'\b(?:use|using|cite|consult|verify|check|with|provide)\b.{0,50}\b(?:official|primary)\s+(?:sources?|documentation|docs?|links?)\b|استخدم\s+(?:المصادر|الوثائق|المراجع)\s+الرسمية',text))

def fallback(question,history=()):
 text=question.strip();lower=text.casefold()
 if requires_sources(question):return 'web.research'
 if re.search(r'^(?:create|generate|draw|paint|صمم|ارسم|أنشئ)\b',lower):return None
 if re.search(r'^(?:explain|define|what (?:is|are)|اشرح|عرف)\b',lower) and not re.search(r'latest|current|today|recent|newest|أحدث|اليوم|آخر|الحالي',lower):return None
 if re.search(r'reference (?:images|photos)|صور مرجعية',lower):return 'web.photos'
 if re.search(r'\b(?:search|find|research|verify|compare|latest|current|today|newest|price|prices|news|release|releases)\b|ابحث|قارن|تحقق|أحدث|أخبار|آخر|أسعار|اليوم',lower):return 'web.research'
 if history and re.search(r'\b(?:it|its|these|those|which|changed|cheaper|faster|smaller)\b|حجمه|ترخيصه|أسرع',lower):return 'web.research'
 return None
