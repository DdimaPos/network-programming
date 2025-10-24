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

## 1. Perf comparison between server types

[test_concurent.py](test_concurent.py) file will send 10 requests for a file and log out the time from request to the moment of response.
Both servers have a delay of 1 second to simulate workflow.

So first of all I run the first server, then run the `test_concurent.py`
```bash
python3 server.py content/ 8080
python3 test_concurrent.py localhost 8080 "text.txt" 10
```

Then run the second server, run the `test_concurent.py`
```bash
python3 serverMultithread.py content/ 8080
python3 test_concurrent.py localhost 8080 "text.txt" 10
```

And below are the results

### Old implementation. Sigle threaded

Even if not all 10 requests were successfully processed, it can be clearly seen that all the requests were processed sequentially. One at a time

```
======================================================================
Testing 10 concurrent requests to http://localhost:8080/text.txt
======================================================================

Request  1: 1.014s - ✓
Request  2: 2.020s - ✓
Request  3: 3.028s - ✓
Request  4: 4.034s - ✓
Request  5: 5.041s - ✓
Request  6: 6.875s - ✓
Error requesting text.txt: [Errno 60] Operation timed out
Error requesting text.txt: [Errno 60] Operation timed out
Error requesting text.txt: [Errno 60] Operation timed out
Error requesting text.txt: [Errno 60] Operation timed out
Request  7: 7.787s - ✗
Request  8: 7.787s - ✗
Request  9: 7.788s - ✗
Request 10: 7.789s - ✗

----------------------------------------------------------------------
STATISTICS:
----------------------------------------------------------------------
Successful requests: 6/10
Total time (wall-clock): 7.792s
Average request time: 5.316s
Min request time: 1.014s
Max request time: 7.789s
Throughput: 1.28 requests/second
----------------------------------------------------------------------
```

### New implementation. Multiple threads

New implementation creates a new thread for each request which allows
to process them concurently (implementation did not involve creating 
physical threads so they are not processed in parallel)

```
======================================================================
Testing 10 concurrent requests to http://localhost:8080/text.txt
======================================================================

Request  1: 1.025s - ✓
Request  2: 1.025s - ✓
Request  3: 1.026s - ✓
Request  4: 1.026s - ✓
Request  5: 1.025s - ✓
Request  6: 1.038s - ✓
Request  7: 1.039s - ✓
Request  8: 1.038s - ✓
Request  9: 1.039s - ✓
Request 10: 1.039s - ✓

----------------------------------------------------------------------
STATISTICS:
----------------------------------------------------------------------
Successful requests: 10/10
Total time (wall-clock): 1.041s
Average request time: 1.032s
Min request time: 1.025s
Max request time: 1.039s
Throughput: 9.61 requests/second
----------------------------------------------------------------------
```

### Hit Counter and the race condition

Hit counter is a variable that stores a dictionary of paths and the number of visits it got. 
This variable is shared between all the users and is initialized at each start up of the server.

When user is requesting a path, then the counter is completed by the following lines:

```python
## did not write it in one line to enforce later race condition easier
old_value = request_counts.get(str(requested_path), 0)
request_counts[str(requested_path)] = old_value + 1
```

### Trigerring the race condition

A race condition occurs when different thread try to modify the same variable at the same time. Since modifying it envolves:

1. Loading the variable value in memory
2. Changing the value itself
3. Assigning the new value to the variable

With wrong timing on the step 1 all the threads will read the same value of the variable, will modify it and load back without 
knowing that other changes occured.

To trigger a race condition I introduced the following line:

```python
old_value = request_counts.get(str(requested_path), 0)
time.sleep(0.001) - # triggers switching contexts
request_counts[str(requested_path)] = old_value + 1
```

and in this case 0.001s of timeout between reading and assigning the new value (during this timeout it will switch to another thread) 
is just enough to see that race condition will occur. For example with the same test script 
requesting text.txt file 10 times, counter shows that it managed to 

<img width="500" height="469" alt="image" src="https://github.com/user-attachments/assets/7b43ab81-838c-487b-8ddc-422fd65bacc6" />

### Fix of race condition

If remove the timeout, then the counter is looking well, BUT this only happens because the program is limited in it's capacity and it is a 
trivial operation. If there will be a scenario that some additional computations will require more time/thousands of threads the race condition will occur.

```python
counts_lock = threading.Lock()
"""Some code, some code...."""
            with counts_lock:
                request_counts[str(requested_path)] += 1

```

Solution to that is locking the counter variable. Locking means that access to that variable will be restricted to other threads until the current one ended the read/write operation on it. In this case there will be no scenarios when multiple threads read/write at the same time a variable value. This will create a queue for them only in accessing the variable, but will not influence the further operation made by the threads
