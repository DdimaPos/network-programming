# Lab 1: HTTP file server with TCP sockets
## Task

To develop an HTTP web server that serves HTML files from a directory. 
It will handle one HTTP request at a time. The server program should take 
the directory to be served as a command-line argument. Your web server should 
accept and parse the HTTP request, read the requested HTML file from the 
directory, create an HTTP response message consisting of the requested file 
preceded by header lines, and then send the response directly to the 
client. If the requested file is not present in the server (or is not 
an HTML file), the server should send an HTTP “404 Not Found” message 
back to the client.

## Installation guide

```bash
git clone https://github.com/DdimaPos/network-programming
cd Lab1/
docker-compose up
```

Visit now the localhost:8080 and see the content that is placed in `content/` directory

## Implementation showcase

The server runs on port 8080 and  
