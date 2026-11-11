const assert=require('node:assert/strict');
const {video}=require('./assets/media-intent.js');
for(const text of ['Animate this picture.','Create a video of a futuristic city.','Could you please make a short clip of waves?','حرك هذه الصورة','أنشئ فيديو عن البحر'])assert.equal(video(text),true,text);
for(const text of ['Explain how to create a video.','How can I animate this picture?','Write Python code to create a video.','Do not create a video.','Tell me about video generation.','Create a picture of a video camera.','What is animation?','لا تحرك الصورة','اشرح كيف تنشئ فيديو'])assert.equal(video(text),false,text);
console.log('Media routing: 14 positive/negative cases passed.');
