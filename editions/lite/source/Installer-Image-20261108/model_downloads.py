"""User-initiated browser downloads; no model weights fetched by this module."""
from urllib.parse import urlsplit
BASE='https://huggingface.co/Jackrong/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-GGUF/resolve/99b43f206bfe6e4e4c311d8fe5bf9b3a9d06d08e/'
LINKS=[('Lite 8GB starting model · Q4_K_M · 5.78 GB',BASE+'DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q4_K_M.gguf'),('Normal 16GB starting model · Q6_K',BASE+'DeepSeek-V4-Pro-Qwen3.5-9B-MTP-Q6_K.gguf'),('Optional matching vision projector · 1.82 GB',BASE+'mmproj-F32.gguf'),('Browse other GGUF models (compatibility varies)','https://huggingface.co/models?library=gguf')]
def open_download(url,opener=None):
 if url not in [item[1] for item in LINKS] or urlsplit(url).scheme!='https' or urlsplit(url).hostname!='huggingface.co':raise ValueError('Unknown model download link.')
 if opener is None:
  import webbrowser
  opener=webbrowser.open
 return opener(url)
def show(parent):
 import tkinter as tk
 from tkinter import ttk
 dialog=tk.Toplevel(parent);dialog.title('Choose your model');dialog.geometry('660x390');dialog.transient(parent);body=ttk.Frame(dialog,padding=20);body.pack(fill='both',expand=True)
 ttk.Label(body,text='Choose your own local AI model',font=('Segoe UI',16,'bold')).pack(anchor='w')
 ttk.Label(body,text='Downloads open in your browser only when you click. After downloading, choose the GGUF with Browse. Or install the app now and choose a model later in Settings. No model is downloaded automatically.',wraplength=610).pack(anchor='w',pady=12)
 for label,url in LINKS:ttk.Button(body,text=label,command=lambda value=url:open_download(value)).pack(anchor='w',fill='x',pady=4)
 ttk.Label(body,text='A projector must match its language model. Different GGUF architectures and memory requirements are not universally supported.',wraplength=610).pack(anchor='w',pady=10)
 ttk.Button(body,text='Done',command=dialog.destroy).pack(anchor='e')
 dialog.bind('<Escape>',lambda event:dialog.destroy())
