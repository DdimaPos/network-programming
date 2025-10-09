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

For the showcase I will share the following directory structure

<img width="360" height="215" alt="image" src="https://github.com/user-attachments/assets/05717d7d-076e-4ba3-8c97-6ce1682d3395" />

Here I have a bunch of images for other reports, a dummy `index.html` and one my report

### Browser client showcase

The server runs on port 8080 and is running like this

<img width="500" height="978" alt="image" src="https://github.com/user-attachments/assets/0bbea5af-cbb0-4b90-a44a-a5f0c4e83d06" />

Then by visiting http://127.0.0.1:8080/ you will see the directory listing of the `content/` directory from the project

<img width="462" height="404" alt="image" src="https://github.com/user-attachments/assets/882e3c1c-d4f0-4529-8a60-4d1005e50971" />

- User can navigate to other directory listings
<img width="504" height="336" alt="image" src="https://github.com/user-attachments/assets/32f6a7a8-1463-4c0d-a6a2-40bcd9c4e00f" />

- User can see the content of html pages
<img width="1273" height="421" alt="image" src="https://github.com/user-attachments/assets/a602868f-bb31-41ae-a9d9-e0d00d61a91d" />

- For png, pdf, txt files the user sees them directly on the page
<img width="2049" height="1149" alt="image" src="https://github.com/user-attachments/assets/9595283e-4e13-41a2-beb8-291c660dbfdf" />

### CLI client showcase

When the user runs the `client.py` and indicated all the positional arguments that are required, the user will save the file in the 
specified directory if it is a blob (png, pdf, docx etc)

<img width="569" height="231" alt="image" src="https://github.com/user-attachments/assets/8e77c28d-b252-4e55-abad-9baf744bb29c" />

Or see the content of what he requested if it is a text or html

<img width="501" height="818" alt="image" src="https://github.com/user-attachments/assets/3ba20f47-b1e9-4a86-941a-bf2b2cc6bc9b" />


### Logging

When the server is running you can see the logs about the requests and the response sent
<img width="1422" height="449" alt="image" src="https://github.com/user-attachments/assets/54ebc6cb-c742-453a-a28e-e620ff10c1b8" />



