import os
# DRY_RUN=1 prints instead of pressing keys (use it for tests and on machines without a display)
if os.getenv("DRY_RUN"):
    def do_action(word): print("ACTION:", word, flush=True)
else:
    import pyautogui
    MAP = {
        "up":    lambda: pyautogui.press("volumeup", presses=5),
        "down":  lambda: pyautogui.press("volumedown", presses=5),
        "left":  lambda: pyautogui.press("left"),        # previous slide
        "right": lambda: pyautogui.press("right"),       # next slide
        "go":    lambda: pyautogui.press("playpause"),
        "stop":  lambda: pyautogui.press("stop"),
        "yes":   lambda: pyautogui.press("enter"),
        "no":    lambda: pyautogui.press("esc"),
        "on":    lambda: pyautogui.press("f5"),          # start slideshow
        "off":   lambda: pyautogui.press("volumemute"),
    }
    def do_action(word):
        print("ACTION:", word); MAP[word]()
