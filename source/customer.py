import os,sys
if '--stop-engine' in sys.argv:
    from runtime import stop_engine
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
