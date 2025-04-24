from locust import HttpUser, task, between

class ServerUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)  # Частота выполнения (3:1)
    def test_get_lyrics(self):
        self.client.get("/get_lyrics?track_name=Hello&artist=Adele")
    
    @task(1)
    def test_find_similar(self):
        self.client.get("/find_similar?track_name=Hello&artist=Adele")