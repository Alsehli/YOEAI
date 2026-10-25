import os,sys
if '--windows-tool-worker' in sys.argv:
    from windows_tools import worker_main
    worker_main()
elif '--web-search-check' in sys.argv:
    from configuration import HOME
    from web_search import diagnostic
    diagnostic(HOME/'web-search-native-check.json')
elif '--stop-engine' in sys.argv:
    from model_modes import stop_current as stop_engine
    stop_engine()
elif '--setup' in sys.argv:
    from agreement_installer import main
    main()
elif '--developer-mode' in sys.argv:
    from configuration import APP_DIR,HOME,read_config
    from developer_mode import main
    main(APP_DIR,read_config(),HOME)
else:
    from text_image_shell import main
    main()
