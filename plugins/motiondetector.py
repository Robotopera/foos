import time
import os
import sys
from inotify_simple import INotify, flags
import numpy as np
import threading
from foos.bus import Event
import video_config
import multiprocessing as mp


class EventGen:
    """Receive movement status from detector, dedup and send events.
    Sends 'movement_detected' at most every 2 second while movement is detected.
    Sends 'people_start_playing' and 'people_stop_playing' (after absence_timeout w/o movement)"""
    def __init__(self, bus, absence_timeout=30, max_interval=2):
        self.absence_timeout = absence_timeout
        self.last_mv = 0
        self.last_mv_event_time = 0
        self.max_interval = max_interval
        self.movement = None
        self.bus = bus

    def reportMovement(self, newmovement):
        now = time.time()
        if newmovement:
            if now - self.last_mv > self.max_interval:
                self.last_mv = now
                self.bus.notify(Event("movement_detected"))
                #print(time.strftime("%H:%M:%S", time.localtime()), "movement_detected")
        else:
            if now - self.last_mv < self.absence_timeout:
                # wait a bit before assuming people have left
                return

        if self.movement != newmovement:
            event = "people_start_playing" if newmovement else "people_stop_playing"
            print(time.strftime("%H:%M:%S", time.localtime()), event)
            self.bus.notify(Event(event))
            self.movement = newmovement


class MotionDetector:
    """Detect motion in a frame"""
    def __init__(self, size, vector_threshold, min_vectors, crop_x, min_frames_movement):
        self.size = size
        self.vector_threshold = vector_threshold
        self.min_vectors = min_vectors
        self.min_frames_movement = min_frames_movement
        self.crop_x = crop_x

    def frame_has_movement(self, frame):
        arr = np.fromstring(frame, np.dtype("2<u2"))
        arr = arr[:, 1].astype('float')
        arr = np.reshape(arr, (self.size[1], self.size[0]))
        arr = arr[:, self.crop_x:-self.crop_x]
        arr = np.square(arr)
        mvs = len(arr[arr > self.vector_threshold])
        has_movement = (mvs > self.min_vectors)
        return has_movement

    def runs(self, l):
        runs = []
        if len(l) == 0:
            return []

        prev = l[0]
        n = 1
        for i in l[1:]:
            if prev == i:
                n += 1
            else:
                runs.append((prev, n))
                n = 1

            prev = i

        runs.append((prev, n))
        return runs

    def readFrame(self, f):
        return f.read(self.size[0] * self.size[1] * 4)

    def chunk_has_movement(self, d):
        #skip first frame
        frame = self.readFrame(d)
        movement_in_frame = []
        while True:
            frame = self.readFrame(d)
            if len(frame) == 0:
                break

            movement_in_frame.append(self.frame_has_movement(frame))

        # get runs of contiguous frames with or without movement
        rs = self.runs(movement_in_frame)
        # append a default value in case there are no frames with movement
        rs.append((True, 0))
        # get the longest run of frames with movement
        streak = max([r[1] for r in rs if r[0]])
        mv = streak >= self.min_frames_movement
        #print("Detected movement: %6s %d/%d" % (mv, streak, self.min_frames_movement))
        return mv


class Plugin:
    def __init__(self, bus):
        self.size = (82, 46)
        self.md = MotionDetector(self.size, 100000, 30, 25, 9)
        self.eg = EventGen(bus)
        self.watch_dir = video_config.fragments_path
        self.prefix = 'mv'
        mp.Process(daemon=True, target=self.run).start()

    def run(self):
        inotify = INotify()
        watch_flags = flags.CLOSE_WRITE
        print("Watching", self.watch_dir)
        wd = inotify.add_watch(self.watch_dir, watch_flags)

        # And see the corresponding events:
        while True:
            events = inotify.read()
            matching = [f.name for f in events if f.name.startswith(self.prefix)]
            if len(matching) > 0:
                # take only the last file
                self.processForMovement(os.path.join(self.watch_dir, matching[-1]))

        inotify.close()

    def processFile(self, f):
        with open(f, 'rb') as d:
            return self.md.chunk_has_movement(d)

    def processForMovement(self, filename):
        has_movement = self.processFile(filename)
        self.eg.reportMovement(has_movement)
