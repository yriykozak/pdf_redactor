import fitz

class LogicalDocument:
    def __init__(self, doc: fitz.Document):
        self.doc = doc
        self.pages = []
        self.parse_document()

    def parse_document(self):
        for page_num in range(len(self.doc)):
            page = self.doc.load_page(page_num)
            words = page.get_text("words")
            self.pages.append({"words": words})

    def get_page_words(self, page_num):
        if 0 <= page_num < len(self.pages):
            return self.pages[page_num]["words"]
        return []

    def edit_word(self, page_num, word_to_edit, new_word_text):
        if 0 <= page_num < len(self.pages):
            page_words = self.pages[page_num]["words"]
            for i, word in enumerate(page_words):
                if word == word_to_edit:
                    new_word = list(word)
                    new_word[4] = new_word_text
                    page_words[i] = tuple(new_word)
                    return True
        return False
