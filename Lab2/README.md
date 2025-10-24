# Lab 2: HTTP file server with TCP sockets

## Task

In this lab, you will make your HTTP server multithreaded, so 
that it can handle multiple connections concurrently. You can 
either create a thread per request, or use a thread pool.
To test it, write a script that makes multiple concurrent requests 
to your server. Add a delay to the request handler to simulate work 
(~1s), make 10 concurrent requests and measure the amount of time in 
which they are handled. Do the same with the single-threaded server 
from the previous lab. Compare the two.

## Installation guide

```bash
git clone https://github.com/DdimaPos/network-programming
cd Lab2/
docker-compose up 

# for local testing
python3 serverMultithread.py content/
```



