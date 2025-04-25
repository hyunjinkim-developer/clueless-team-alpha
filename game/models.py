from django.db import models
import json

class Game(models.Model):
    case_file = models.JSONField()  # Stores the solution: {"suspect": "", "room": "", "weapon": ""}
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    players_list = models.JSONField(default=list) # Username ever joined the game
    begun = models.BooleanField(default=False)

    def __str__(self):
        return f"Game {self.id} - {'Active' if self.is_active else 'Inactive'}/ Players ever joined: {self.players_list}"

class Player(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players')
    username = models.CharField(max_length=150)
    character = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    turn = models.BooleanField(default=False)
    hand = models.JSONField(default=list)
    moved = models.BooleanField(default=False)  # Indicates if the player has moved
    accused = models.BooleanField(default=False)  # Indicates if the player has accused someone
    suggested = models.BooleanField(default=False)  # Indicates if the player has been moved to the suggestion room

    def __str__(self):
        return f"{self.username} as {self.character} in Game {self.game.id}"