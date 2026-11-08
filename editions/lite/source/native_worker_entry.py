import sys,json,ctypes as C
if '--probe' in sys.argv:
 from native_ai.libllama import Library
 lib=Library(sys.argv[sys.argv.index('--probe')+1]);g=lib.ggml;base=C.CDLL(str(lib.directory/'ggml-base.dll'))
 g.ggml_backend_dev_count.restype=C.c_size_t;g.ggml_backend_dev_get.argtypes=[C.c_size_t];g.ggml_backend_dev_get.restype=C.c_void_p
 base.ggml_backend_dev_name.argtypes=[C.c_void_p];base.ggml_backend_dev_name.restype=C.c_char_p
 names=[base.ggml_backend_dev_name(g.ggml_backend_dev_get(i)).decode()for i in range(g.ggml_backend_dev_count())]
 result={'native':True,'devices':names,'cuda':any(n.startswith('CUDA')for n in names),'modelLoaded':False,'transport':'none'}
 lib.backend_free();print(json.dumps(result));sys.exit(0 if result['cuda']else 1)
else:
 from native_ai.worker import main
 main()
