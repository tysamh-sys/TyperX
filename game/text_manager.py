import os
import random
import re

class TextManager:
    def __init__(self, custom_text_path=None):
        if custom_text_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.custom_text_path = os.path.join(base_dir, "data", "custom_text.txt")
        else:
            self.custom_text_path = custom_text_path
            
        # Level Themed Vocabularies (Easy -> Hard)
        self.themed_vocab = {
            1: ["star", "moon", "nova", "orbit", "dust", "solar", "alien", "rover", "comet", "space", "ship", "void", "core", "hull", "warp"],
            2: ["frost", "chill", "cold", "snow", "sleet", "glacier", "tundra", "frozen", "shiver", "iceberg", "freeze", "blizzard", "arctic", "winter"],
            3: ["magma", "lava", "fire", "ash", "heat", "burn", "flame", "melt", "smoke", "crater", "cinder", "caldera", "obsidian", "eruption", "volcano"],
            4: ["spell", "magic", "rune", "wand", "mage", "elixir", "scroll", "tome", "staff", "castle", "potion", "wizard", "alchemy", "fantasy", "grimoire"],
            5: ["cyber", "code", "data", "byte", "hacker", "binary", "matrix", "vector", "signal", "network", "system", "decrypt", "encrypt", "override", "protocol"]
        }
        
        # Level Boss Sentences
        self.boss_sentences = {
            1: "activate core thrusters and escape orbit",
            2: "charge thermal heaters to melt the ice wall",
            3: "deploy carbon shields to contain the magma flow",
            4: "awaken ancient magical circles of power",
            5: "override security protocols and decrypt the database"
        }
        
        self.custom_words = []
        self.custom_sentences = []
        self.use_custom = False
        
        # Load fallback default custom text if no db custom text is loaded yet
        self.load_default_custom_words()

    def load_default_custom_words(self):
        try:
            if os.path.exists(self.custom_text_path):
                with open(self.custom_text_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    words, sentences = self.parse_text(content)
                    self.custom_words = words
                    # Default file might just be words, so sentences might be empty. That's fine.
                    self.custom_sentences = sentences
        except Exception as e:
            print(f"Error loading default words from {self.custom_text_path}: {e}")

    @staticmethod
    def parse_text(text_content):
        """Extract valid words and boss sentences from raw text."""
        # Words: alphabetic, length 3 to 19
        raw_words = re.findall(r'[a-zA-Z]+', text_content)
        words = []
        seen_words = set()
        for w in raw_words:
            w_low = w.lower()
            if 2 < len(w_low) < 20 and w_low not in seen_words:
                words.append(w_low)
                seen_words.add(w_low)
                
        # Sentences: length 15 to 60 chars, 3 to 8 words, spaces and alphabetic characters only
        raw_sentences = re.split(r'[.!?\n]+', text_content)
        sentences = []
        seen_sentences = set()
        for s in raw_sentences:
            s_clean = re.sub(r'\s+', ' ', s).strip()
            # Clean punctuation/digits, keep only letters and spaces
            s_alpha = re.sub(r'[^a-zA-Z\s]', '', s_clean).strip().lower()
            s_alpha = re.sub(r'\s+', ' ', s_alpha)
            if not s_alpha:
                continue
            words_in_s = s_alpha.split()
            if 3 <= len(words_in_s) <= 8 and 12 <= len(s_alpha) <= 60:
                if s_alpha not in seen_sentences:
                    sentences.append(s_alpha)
                    seen_sentences.add(s_alpha)
                    
        return words, sentences

    def set_custom_data(self, words, sentences, use_custom):
        self.custom_words = words
        self.custom_sentences = sentences
        self.use_custom = use_custom

    def get_random_word(self, level=1, difficulty="medium"):
        # Cycle themes above level 5
        level_index = (level - 1) % 5 + 1
        theme_pool = self.themed_vocab[level_index]
        
        # Word length filters based on difficulty
        if difficulty == "beginner":
            min_len = 3
            max_len = 5
        elif difficulty == "hard":
            min_len = 6 + (level_index // 2)
            max_len = 10 + (level_index * 2)
        else: # medium
            min_len = 3 + (level_index // 3)
            max_len = 5 + (level_index * 2)
            
        if self.use_custom and self.custom_words:
            custom_pool = [w for w in self.custom_words if min_len <= len(w) <= max_len]
            if custom_pool:
                # 85% chance to use custom words if available, 15% theme pool for variety
                if random.random() < 0.85:
                    return random.choice(custom_pool)
                    
        # Filter theme pool by length if possible
        filtered_theme = [w for w in theme_pool if min_len - 1 <= len(w) <= max_len + 1]
        if filtered_theme:
            return random.choice(filtered_theme)
        return random.choice(theme_pool)

    def get_boss_sentence(self, level=1):
        level_index = (level - 1) % 5 + 1
        if self.use_custom and self.custom_sentences:
            return random.choice(self.custom_sentences)
        return self.boss_sentences.get(level_index, "override security and secure the mainframe")

