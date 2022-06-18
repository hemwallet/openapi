import uvicorn


if __name__ == '__main__':
    from openapi import app, start_cache, stop_cache
    start_cache()
    uvicorn.run(
        app, host="0.0.0.0", port=17500, reload=False,
        # ssl_keyfile='', ssl_certfile=''
    )
    stop_cache()
