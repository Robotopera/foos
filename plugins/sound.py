#!/usr/bin/env python
import time
import subprocess
import random
import os


class Plugin:
    # This map scores => sounds
    sounds = {
        'X_0_win': ['Boxing_arena_sound-Samantha_Enrico-246597508', 'Morse Code-SoundBible.com-810471357'],
        '1_goal_left': ['musical035', 'musical041', 'musical105']
    }
    generic_goal_sounds = ['crowd1', 'crowd2']

    def __init__(self, bus):
        self.bus = bus
        self.bus.subscribe(self.process_event, thread=True)
        self.rand = random.Random()
        root = os.path.abspath(os.path.dirname(__file__))
        self.sounds_dir = root + "/../sounds"
        self.running = []
        self.game_mode = None

    def wait_for(self):
        still_running = []
        for p in self.running:
            try:
                p.wait(timeout=0)
            except subprocess.TimeoutExpired:
                still_running.append(p)

        self.running = still_running

    def play(self, s):
        self.wait_for()
        p = subprocess.Popen(['play', '-V0', '-q', s])
        self.running.append(p)

    def process_event(self, ev):
        sounds = []
        if ev.name == 'set_game_mode':
            self.game_mode = ev.data['mode']
        if ev.name == 'score_goal':
            score = sorted((ev.data['yellow'], ev.data['black']))
            if self.game_mode is not None:
                if score[0] == score[1] and score[0] == self.game_mode - 1:
                    sounds.append(self.rand.choice(self.sounds['1_goal_left']))

                if score[0] == 0 and score[1] == self.game_mode:
                    sounds.append(self.rand.choice(self.sounds['X_0_win']))

            sounds.append(self.rand.choice(self.generic_goal_sounds))

        elif ev.name == 'score_reset':
            sounds = [self.rand.choice(['whistle_2short1long', 'Air Horn-SoundBible.com-964603082'])]
        else:
            return

        sounds = [self.sounds_dir + "/{}.wav".format(sound) for sound in sounds]

        for s in sounds:
            self.play(s)


if __name__ == "__main__":
    sc = SoundController()
    for i in range(6):
        score = (i, 0)
        print(score)
        sc.update(score)
        time.sleep(2)

    for i in range(6):
        score = (0, i)
        print(score)
        sc.update(score)
        time.sleep(2)
    sc.update((4, 4))
    time.sleep(3)
