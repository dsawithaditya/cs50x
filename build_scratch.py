import json
import hashlib
import zipfile
import wave
import struct
import math
import os

def create_wav_sound():
    """Generates a pleasant 880Hz 'ding/coin' wav sound."""
    sample_rate = 22050
    duration = 0.25  # seconds
    num_samples = int(sample_rate * duration)
    wav_bytes = bytearray()
    
    import io
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        frames = []
        for i in range(num_samples):
            t = i / sample_rate
            # 880 Hz decaying sine wave (pleasant chime)
            envelope = math.exp(-12 * t)
            freq = 880 if t < 0.1 else 1320
            val = int(32767 * 0.7 * envelope * math.sin(2 * math.pi * freq * t))
            frames.append(struct.pack('<h', max(-32768, min(32767, val))))
        wav_file.writeframes(b''.join(frames))
    
    return buffer.getvalue()

def build_project():
    # 1. Assets
    # Backdrop: Space / Night Sky with subtle stars
    backdrop_svg = """<svg version="1.1" width="480" height="360" viewBox="0 0 480 360" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="sky" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#05051e"/>
      <stop offset="60%" stop-color="#0b1335"/>
      <stop offset="100%" stop-color="#192854"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="480" height="360" fill="url(#sky)"/>
  <!-- Distant Stars -->
  <circle cx="45" cy="40" r="1.5" fill="#fff" opacity="0.8"/>
  <circle cx="95" cy="110" r="1" fill="#90caf9" opacity="0.7"/>
  <circle cx="150" cy="50" r="2" fill="#fff" opacity="0.9"/>
  <circle cx="210" cy="90" r="1" fill="#fff" opacity="0.6"/>
  <circle cx="280" cy="35" r="2.5" fill="#ffe082" opacity="0.9"/>
  <circle cx="340" cy="120" r="1.5" fill="#fff" opacity="0.8"/>
  <circle cx="410" cy="65" r="1" fill="#90caf9" opacity="0.7"/>
  <circle cx="450" cy="140" r="2" fill="#fff" opacity="0.8"/>
  <circle cx="70" cy="200" r="1.5" fill="#fff" opacity="0.6"/>
  <circle cx="160" cy="240" r="1" fill="#ffe082" opacity="0.7"/>
  <circle cx="240" cy="180" r="2" fill="#fff" opacity="0.9"/>
  <circle cx="320" cy="230" r="1" fill="#fff" opacity="0.6"/>
  <circle cx="390" cy="210" r="1.5" fill="#90caf9" opacity="0.8"/>
  <circle cx="440" cy="270" r="2" fill="#fff" opacity="0.7"/>
  <!-- Moon / Nebula glow -->
  <circle cx="400" cy="60" r="28" fill="#ffeaa7" opacity="0.85"/>
  <circle cx="408" cy="56" r="24" fill="#0b1335"/>
</svg>"""

    # Sprite 1: Spaceship / Rocket
    rocket_svg = """<svg version="1.1" width="60" height="70" viewBox="0 0 60 70" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#3b82f6"/>
      <stop offset="50%" stop-color="#60a5fa"/>
      <stop offset="100%" stop-color="#1d4ed8"/>
    </linearGradient>
    <linearGradient id="finGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ef4444"/>
      <stop offset="100%" stop-color="#b91c1c"/>
    </linearGradient>
    <linearGradient id="flameGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#fbbf24"/>
      <stop offset="100%" stop-color="#ef4444"/>
    </linearGradient>
  </defs>
  <!-- Flame -->
  <polygon points="25,58 35,58 30,68" fill="url(#flameGrad)"/>
  <!-- Left Fin -->
  <polygon points="20,42 8,56 22,54" fill="url(#finGrad)"/>
  <!-- Right Fin -->
  <polygon points="40,42 52,56 38,54" fill="url(#finGrad)"/>
  <!-- Rocket Body -->
  <path d="M 30,4 C 38,15 42,32 40,54 L 20,54 C 18,32 22,15 30,4 Z" fill="url(#bodyGrad)"/>
  <!-- Cockpit Window -->
  <circle cx="30" cy="24" r="7" fill="#38bdf8" stroke="#ffffff" stroke-width="2"/>
  <circle cx="28" cy="22" r="2.5" fill="#ffffff" opacity="0.8"/>
  <!-- Nosecone tip -->
  <path d="M 30,4 C 33,8 35,14 35,16 L 25,16 C 25,14 27,8 30,4 Z" fill="#ef4444"/>
</svg>"""

    # Sprite 2: Star (Collectible)
    star_svg = """<svg version="1.1" width="44" height="44" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="starGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fef08a"/>
      <stop offset="50%" stop-color="#facc15"/>
      <stop offset="100%" stop-color="#eab308"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="1.5" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <!-- 5-pointed Star -->
  <polygon points="22,3 27.5,15 41,16.5 30.5,26 33.5,39.5 22,32.5 10.5,39.5 13.5,26 3,16.5 16.5,15"
           fill="url(#starGrad)" stroke="#ca8a04" stroke-width="1.5" filter="url(#glow)"/>
  <!-- Inner Highlight -->
  <circle cx="20" cy="18" r="3" fill="#ffffff" opacity="0.7"/>
</svg>"""

    # Generate WAV sound
    coin_wav = create_wav_sound()

    # MD5s
    bd_bytes = backdrop_svg.encode('utf-8')
    bd_md5 = hashlib.md5(bd_bytes).hexdigest()

    rocket_bytes = rocket_svg.encode('utf-8')
    rocket_md5 = hashlib.md5(rocket_bytes).hexdigest()

    star_bytes = star_svg.encode('utf-8')
    star_md5 = hashlib.md5(star_bytes).hexdigest()

    wav_md5 = hashlib.md5(coin_wav).hexdigest()

    # Variable ID
    var_score_id = "`j98fs7d-score"

    # Assemble targets
    # 1. Stage Target
    stage = {
        "isStage": True,
        "name": "Stage",
        "variables": {
            var_score_id: ["score", 0]
        },
        "lists": {},
        "broadcasts": {},
        "customVars": [],
        "blocks": {},
        "comments": {},
        "currentCostume": 0,
        "costumes": [
            {
                "name": "SpaceBackdrop",
                "dataFormat": "svg",
                "assetId": bd_md5,
                "md5ext": f"{bd_md5}.svg",
                "rotationCenterX": 240,
                "rotationCenterY": 180
            }
        ],
        "sounds": [],
        "volume": 100,
        "layerOrder": 0,
        "tempo": 60,
        "videoTransparency": 50,
        "videoState": "on",
        "textToSpeechLanguage": None
    }

    # 2. Spaceship Target
    # Scripts for Spaceship:
    # Script A (Flag):
    #   When green flag clicked
    #   set score to 0
    #   go to x: 0, y: -130
    #   say "Use Left & Right Arrows! Press Space for Turbo!" for 2 secs
    #   forever:
    #     if key Right Arrow pressed:
    #       change x by 8
    #     if key Left Arrow pressed:
    #       change x by -8
    #     if on edge, bounce
    #
    # Script B (Space key):
    #   When space key pressed
    #   call turbo_boost(15)
    #
    # Script C (Turbo Boost definition - custom block):
    #   define turbo_boost (boost_amount)
    #     change x by boost_amount
    #     change x by -boost_amount (quick pulse/dash)
    #
    rocket_blocks = {
        # --- Script A: Green Flag ---
        "r_flag": {
            "opcode": "event_whenflagclicked",
            "next": "r_set_score",
            "parent": None,
            "inputs": {},
            "fields": {},
            "shadow": False,
            "topLevel": True,
            "x": 40,
            "y": 40
        },
        "r_set_score": {
            "opcode": "data_setvariableto",
            "next": "r_goto_start",
            "parent": "r_flag",
            "inputs": {
                "VALUE": [1, [4, "0"]]
            },
            "fields": {
                "VARIABLE": ["score", var_score_id]
            },
            "shadow": False,
            "topLevel": False
        },
        "r_goto_start": {
            "opcode": "motion_gotoxy",
            "next": "r_say_intro",
            "parent": "r_set_score",
            "inputs": {
                "X": [1, [4, "0"]],
                "Y": [1, [4, "-130"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "r_say_intro": {
            "opcode": "looks_sayforsecs",
            "next": "r_loop",
            "parent": "r_goto_start",
            "inputs": {
                "MESSAGE": [1, [10, "Catch falling stars! Arrows to move, Space to boost!"]],
                "SECS": [1, [4, "2"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "r_loop": {
            "opcode": "control_forever",
            "next": None,
            "parent": "r_say_intro",
            "inputs": {
                "SUBSTACK": [2, "r_if_right"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        # if key right pressed:
        "r_if_right": {
            "opcode": "control_if",
            "next": "r_if_left",
            "parent": "r_loop",
            "inputs": {
                "CONDITION": [2, "r_key_right"],
                "SUBSTACK": [2, "r_move_right"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "r_key_right": {
            "opcode": "sensing_keypressed",
            "next": None,
            "parent": "r_if_right",
            "inputs": {
                "KEY_OPTION": [1, "r_opt_right"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "r_opt_right": {
            "opcode": "sensing_keyoptions",
            "next": None,
            "parent": "r_key_right",
            "inputs": {},
            "fields": {
                "KEY_OPTION": ["right arrow", None]
            },
            "shadow": True,
            "topLevel": False
        },
        "r_move_right": {
            "opcode": "motion_changexby",
            "next": None,
            "parent": "r_if_right",
            "inputs": {
                "DX": [1, [4, "8"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        # if key left pressed:
        "r_if_left": {
            "opcode": "control_if",
            "next": "r_bounce",
            "parent": "r_if_right",
            "inputs": {
                "CONDITION": [2, "r_key_left"],
                "SUBSTACK": [2, "r_move_left"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "r_key_left": {
            "opcode": "sensing_keypressed",
            "next": None,
            "parent": "r_if_left",
            "inputs": {
                "KEY_OPTION": [1, "r_opt_left"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "r_opt_left": {
            "opcode": "sensing_keyoptions",
            "next": None,
            "parent": "r_key_left",
            "inputs": {},
            "fields": {
                "KEY_OPTION": ["left arrow", None]
            },
            "shadow": True,
            "topLevel": False
        },
        "r_move_left": {
            "opcode": "motion_changexby",
            "next": None,
            "parent": "r_if_left",
            "inputs": {
                "DX": [1, [4, "-8"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        # bounce if on edge:
        "r_bounce": {
            "opcode": "motion_ifonedgebounce",
            "next": None,
            "parent": "r_if_left",
            "inputs": {},
            "fields": {},
            "shadow": False,
            "topLevel": False
        },

        # --- Script B: When Space Key Pressed ---
        "r_space_key": {
            "opcode": "event_whenkeypressed",
            "next": "r_call_boost",
            "parent": None,
            "inputs": {},
            "fields": {
                "KEY_OPTION": ["space", None]
            },
            "shadow": False,
            "topLevel": True,
            "x": 40,
            "y": 420
        },
        "r_call_boost": {
            "opcode": "procedures_call",
            "next": None,
            "parent": "r_space_key",
            "inputs": {
                "arg_boost": [1, [4, "25"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "proccode": "turbo boost %n",
                "argumentids": "[\"arg_boost\"]",
                "warp": "false"
            }
        },

        # --- Script C: Turbo Boost Custom Block Definition ---
        "r_proc_def": {
            "opcode": "procedures_definition",
            "next": "r_boost_action",
            "parent": None,
            "inputs": {
                "custom_block": [1, "r_proc_proto"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": True,
            "x": 40,
            "y": 550
        },
        "r_proc_proto": {
            "opcode": "procedures_prototype",
            "next": None,
            "parent": "r_proc_def",
            "inputs": {
                "arg_boost": [1, "r_proto_arg"]
            },
            "fields": {},
            "shadow": True,
            "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "proccode": "turbo boost %n",
                "argumentids": "[\"arg_boost\"]",
                "argumentnames": "[\"boost_amount\"]",
                "argumentdefaults": "[\"25\"]",
                "warp": "false"
            }
        },
        "r_proto_arg": {
            "opcode": "argument_reporter_string_number",
            "next": None,
            "parent": "r_proc_proto",
            "inputs": {},
            "fields": {
                "VALUE": ["boost_amount", None]
            },
            "shadow": True,
            "topLevel": False
        },
        "r_boost_action": {
            "opcode": "motion_changexby",
            "next": None,
            "parent": "r_proc_def",
            "inputs": {
                "DX": [3, "r_use_boost_arg", [4, "25"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "r_use_boost_arg": {
            "opcode": "argument_reporter_string_number",
            "next": None,
            "parent": "r_boost_action",
            "inputs": {},
            "fields": {
                "VALUE": ["boost_amount", None]
            },
            "shadow": False,
            "topLevel": False
        }
    }

    rocket_target = {
        "isStage": False,
        "name": "Spaceship",
        "variables": {},
        "lists": {},
        "broadcasts": {},
        "blocks": rocket_blocks,
        "comments": {},
        "currentCostume": 0,
        "costumes": [
            {
                "name": "rocket",
                "dataFormat": "svg",
                "assetId": rocket_md5,
                "md5ext": f"{rocket_md5}.svg",
                "rotationCenterX": 30,
                "rotationCenterY": 35
            }
        ],
        "sounds": [],
        "volume": 100,
        "layerOrder": 1,
        "visible": True,
        "x": 0,
        "y": -130,
        "size": 100,
        "direction": 90,
        "draggable": False,
        "rotationStyle": "don't rotate"
    }

    # 3. Star Target
    # Scripts for Star:
    # Script D (Flag):
    #   When green flag clicked:
    #     go to x: pick random -200 to 200, y: 160
    #     forever:
    #       change y by -5
    #       if touching Spaceship:
    #         call add_score(1)
    #       if y position < -160:
    #         go to x: pick random -200 to 200, y: 160
    #
    # Script E (add_score Custom Block Definition with 1 input):
    #   define add_score (points)
    #     change score by points
    #     start sound Chime
    #     go to x: pick random -200 to 200, y: 160
    #
    star_blocks = {
        # --- Script D: Flag ---
        "s_flag": {
            "opcode": "event_whenflagclicked",
            "next": "s_goto_top",
            "parent": None,
            "inputs": {},
            "fields": {},
            "shadow": False,
            "topLevel": True,
            "x": 40,
            "y": 40
        },
        "s_goto_top": {
            "opcode": "motion_gotoxy",
            "next": "s_loop",
            "parent": "s_flag",
            "inputs": {
                "X": [3, "s_rand_x_init", [4, "0"]],
                "Y": [1, [4, "160"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_rand_x_init": {
            "opcode": "operator_random",
            "next": None,
            "parent": "s_goto_top",
            "inputs": {
                "FROM": [1, [4, "-200"]],
                "TO": [1, [4, "200"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_loop": {
            "opcode": "control_forever",
            "next": None,
            "parent": "s_goto_top",
            "inputs": {
                "SUBSTACK": [2, "s_fall"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_fall": {
            "opcode": "motion_changeyby",
            "next": "s_if_touching",
            "parent": "s_loop",
            "inputs": {
                "DY": [1, [4, "-5"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        # if touching Spaceship:
        "s_if_touching": {
            "opcode": "control_if",
            "next": "s_if_bottom",
            "parent": "s_fall",
            "inputs": {
                "CONDITION": [2, "s_touching_rocket"],
                "SUBSTACK": [2, "s_call_add_score"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_touching_rocket": {
            "opcode": "sensing_touchingobject",
            "next": None,
            "parent": "s_if_touching",
            "inputs": {
                "TOUCHINGOBJECTMENU": [1, "s_menu_rocket"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_menu_rocket": {
            "opcode": "sensing_touchingobjectmenu",
            "next": None,
            "parent": "s_touching_rocket",
            "inputs": {},
            "fields": {
                "TOUCHINGOBJECTMENU": ["Spaceship", None]
            },
            "shadow": True,
            "topLevel": False
        },
        "s_call_add_score": {
            "opcode": "procedures_call",
            "next": None,
            "parent": "s_if_touching",
            "inputs": {
                "arg_pts": [1, [4, "1"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "proccode": "add score %n",
                "argumentids": "[\"arg_pts\"]",
                "warp": "false"
            }
        },
        # if y position < -160:
        "s_if_bottom": {
            "opcode": "control_if",
            "next": None,
            "parent": "s_if_touching",
            "inputs": {
                "CONDITION": [2, "s_lt_bottom"],
                "SUBSTACK": [2, "s_respawn_bottom"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_lt_bottom": {
            "opcode": "operator_lt",
            "next": None,
            "parent": "s_if_bottom",
            "inputs": {
                "OPERAND1": [3, "s_ypos", [10, ""]],
                "OPERAND2": [1, [4, "-160"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_ypos": {
            "opcode": "motion_yposition",
            "next": None,
            "parent": "s_lt_bottom",
            "inputs": {},
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_respawn_bottom": {
            "opcode": "motion_gotoxy",
            "next": None,
            "parent": "s_if_bottom",
            "inputs": {
                "X": [3, "s_rand_x_respawn", [4, "0"]],
                "Y": [1, [4, "160"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_rand_x_respawn": {
            "opcode": "operator_random",
            "next": None,
            "parent": "s_respawn_bottom",
            "inputs": {
                "FROM": [1, [4, "-200"]],
                "TO": [1, [4, "200"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },

        # --- Script E: Custom block add_score(points) definition ---
        "s_def": {
            "opcode": "procedures_definition",
            "next": "s_change_score",
            "parent": None,
            "inputs": {
                "custom_block": [1, "s_proto"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": True,
            "x": 40,
            "y": 420
        },
        "s_proto": {
            "opcode": "procedures_prototype",
            "next": None,
            "parent": "s_def",
            "inputs": {
                "arg_pts": [1, "s_proto_arg"]
            },
            "fields": {},
            "shadow": True,
            "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "proccode": "add score %n",
                "argumentids": "[\"arg_pts\"]",
                "argumentnames": "[\"points\"]",
                "argumentdefaults": "[\"1\"]",
                "warp": "false"
            }
        },
        "s_proto_arg": {
            "opcode": "argument_reporter_string_number",
            "next": None,
            "parent": "s_proto",
            "inputs": {},
            "fields": {
                "VALUE": ["points", None]
            },
            "shadow": True,
            "topLevel": False
        },
        # Procedure body block 1: change score by points
        "s_change_score": {
            "opcode": "data_changevariableby",
            "next": "s_play_sound",
            "parent": "s_def",
            "inputs": {
                "VALUE": [3, "s_use_arg", [4, "1"]]
            },
            "fields": {
                "VARIABLE": ["score", var_score_id]
            },
            "shadow": False,
            "topLevel": False
        },
        "s_use_arg": {
            "opcode": "argument_reporter_string_number",
            "next": None,
            "parent": "s_change_score",
            "inputs": {},
            "fields": {
                "VALUE": ["points", None]
            },
            "shadow": False,
            "topLevel": False
        },
        # Procedure body block 2: play sound
        "s_play_sound": {
            "opcode": "sound_play",
            "next": "s_respawn_after_catch",
            "parent": "s_change_score",
            "inputs": {
                "SOUND_MENU": [1, "s_sound_menu"]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_sound_menu": {
            "opcode": "sound_sounds_menu",
            "next": None,
            "parent": "s_play_sound",
            "inputs": {},
            "fields": {
                "SOUND_MENU": ["Chime", None]
            },
            "shadow": True,
            "topLevel": False
        },
        # Procedure body block 3: respawn at top
        "s_respawn_after_catch": {
            "opcode": "motion_gotoxy",
            "next": None,
            "parent": "s_play_sound",
            "inputs": {
                "X": [3, "s_rand_x_caught", [4, "0"]],
                "Y": [1, [4, "160"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        },
        "s_rand_x_caught": {
            "opcode": "operator_random",
            "next": None,
            "parent": "s_respawn_after_catch",
            "inputs": {
                "FROM": [1, [4, "-200"]],
                "TO": [1, [4, "200"]]
            },
            "fields": {},
            "shadow": False,
            "topLevel": False
        }
    }

    star_target = {
        "isStage": False,
        "name": "Star",
        "variables": {},
        "lists": {},
        "broadcasts": {},
        "blocks": star_blocks,
        "comments": {},
        "currentCostume": 0,
        "costumes": [
            {
                "name": "star",
                "dataFormat": "svg",
                "assetId": star_md5,
                "md5ext": f"{star_md5}.svg",
                "rotationCenterX": 22,
                "rotationCenterY": 22
            }
        ],
        "sounds": [
            {
                "name": "Chime",
                "assetId": wav_md5,
                "dataFormat": "wav",
                "format": "",
                "rate": 22050,
                "sampleCount": len(coin_wav) // 2,
                "md5ext": f"{wav_md5}.wav"
            }
        ],
        "volume": 100,
        "layerOrder": 2,
        "visible": True,
        "x": 0,
        "y": 160,
        "size": 90,
        "direction": 90,
        "draggable": False,
        "rotationStyle": "all around"
    }

    # Monitors (for score variable)
    monitors = [
        {
            "id": var_score_id,
            "mode": "default",
            "opcode": "data_variable",
            "params": {
                "VARIABLE": "score"
            },
            "spriteName": None,
            "value": 0,
            "width": 0,
            "height": 0,
            "x": 10,
            "y": 10,
            "visible": True,
            "sliderMin": 0,
            "sliderMax": 100,
            "isDiscrete": True
        }
    ]

    project_data = {
        "targets": [stage, rocket_target, star_target],
        "monitors": monitors,
        "extensionData": {},
        "extensions": [],
        "meta": {
            "semver": "3.0.0",
            "vm": "0.2.0",
            "agent": "Mozilla/5.0"
        }
    }

    # Create .sb3 archive
    output_filename = "project.sb3"
    with zipfile.ZipFile(output_filename, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", json.dumps(project_data, indent=2))
        z.writestr(f"{bd_md5}.svg", bd_bytes)
        z.writestr(f"{rocket_md5}.svg", rocket_bytes)
        z.writestr(f"{star_md5}.svg", star_bytes)
        z.writestr(f"{wav_md5}.wav", coin_wav)

    print(f"Successfully generated {output_filename}")
    return output_filename

if __name__ == "__main__":
    build_project()
