#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from typing import Dict, List, Set, Optional
from difflib import SequenceMatcher
import unicodedata

class TurkishSpellChecker:
    """
    Türkçe arama sorguları için spell checker.
    Yaygın yazım hatalarını düzeltir ve önerilerde bulunur.
    """
    
    def __init__(self):
        # Türkçe yaygın kelimeler ve ürün kategorileri
        self.dictionary = {
            # Giyim kategorisi
            'giyim', 'elbise', 'pantolon', 'gömlek', 'tişört', 'kazak', 'mont', 'ceket', 
            'kaban', 'ayakkabı', 'bot', 'sandalet', 'terlik', 'çanta', 'şapka', 'kemer',
            'etek', 'şort', 'jean', 'kot', 'bluz', 'tunik', 'yelek', 'hirka', 'sweatshirt',
            
            # Kozmetik kategorisi
            'kozmetik', 'makyaj', 'ruj', 'rimel', 'fondöten', 'pudra', 'allık', 'göz',
            'kalem', 'far', 'parfüm', 'şampuan', 'krem', 'losyon', 'sabun', 'nemlendirici',
            'temizleyici', 'tonik', 'maske', 'serum', 'güneş', 'bronzlaştırıcı',
            
            # Elektronik kategorisi
            'telefon', 'bilgisayar', 'laptop', 'tablet', 'kulaklık', 'şarj', 'kılıf',
            'kamera', 'oyun', 'konsol', 'televizyon', 'hoparlör', 'mouse', 'klavye',
            'monitor', 'harddisk', 'bellek', 'işlemci', 'anakart', 'ekran', 'batarya',
            
            # Ev kategorisi
            'mutfak', 'banyo', 'yatak', 'salon', 'masa', 'sandalye', 'dolap', 'raf',
            'lamba', 'halı', 'perde', 'yastık', 'battaniye', 'çarşaf', 'havlu', 'tabak',
            'bardak', 'kaşık', 'çatal', 'bıçak', 'tencere', 'tava', 'fırın', 'buzdolabı',
            
            # Spor kategorisi
            'spor', 'ayakkabı', 'koşu', 'fitness', 'yoga', 'futbol', 'basketbol', 'tenis',
            'yüzme', 'dalış', 'kamp', 'outdoor', 'bisiklet', 'kaykay', 'paten', 'dağcılık',
            
            # Yaygın modifierlar
            'erkek', 'kadın', 'çocuk', 'bebek', 'kız', 'oğlan', 'unisex', 'büyük', 'küçük',
            'orta', 'xl', 'medium', 'large', 'small', 'siyah', 'beyaz', 'kırmızı', 'mavi',
            'sarı', 'yeşil', 'mor', 'pembe', 'gri', 'kahverengi', 'turuncu', 'lacivert',
            'bordo', 'bej', 'altın', 'gümüş', 'bronz', 'şeffaf', 'mat', 'parlak',
            
            # Markalar (örnek)
            'nike', 'adidas', 'puma', 'samsung', 'apple', 'xiaomi', 'huawei', 'oppo',
            'vivo', 'realme', 'lg', 'sony', 'zara', 'mango', 'koton', 'lcw', 'defacto',
        }
        
        # Yaygın yazım hataları ve düzeltmeleri
        self.corrections = {
            # Türkçe karakter hataları
            'kozmetık': 'kozmetik',
            'gıyım': 'giyim',
            'giyım': 'giyim',
            'telefon': 'telefon',
            'bılgısayar': 'bilgisayar',
            'bilgisayar': 'bilgisayar',
            'ayakabı': 'ayakkabı',
            'ayakkabı': 'ayakkabı',
            'çocuk': 'çocuk',
            'cocuk': 'çocuk',
            'kadın': 'kadın',
            'kadin': 'kadın',
            'erkek': 'erkek',
            'sıyah': 'siyah',
            'siyah': 'siyah',
            'beyaz': 'beyaz',
            'kırmızı': 'kırmızı',
            'kirmizi': 'kırmızı',
            'mavı': 'mavi',
            'mavi': 'mavi',
            'yeşıl': 'yeşil',
            'yesil': 'yeşil',
            'sarı': 'sarı',
            'sari': 'sarı',
            
            # İngilizce-Türkçe karışımları
            'phone': 'telefon',
            'computer': 'bilgisayar',
            'laptop': 'laptop',
            'shoes': 'ayakkabı',
            'dress': 'elbise',
            'shirt': 'gömlek',
            'pants': 'pantolon',
            'bag': 'çanta',
            'black': 'siyah',
            'white': 'beyaz',
            'red': 'kırmızı',
            'blue': 'mavi',
            'green': 'yeşil',
            'yellow': 'sarı',
            
            # Yaygın typo'lar
            'giyim': 'giyim',
            'gyim': 'giyim',
            'giim': 'giyim',
            'giyim': 'giyim',
            'kozmetık': 'kozmetik',
            'kozmetic': 'kozmetik',
            'kozmetıc': 'kozmetik',
            'teleofn': 'telefon',
            'teleon': 'telefon',
            'telfon': 'telefon',
            'bilgisaar': 'bilgisayar',
            'bilgisayar': 'bilgisayar',
            'bılgısayar': 'bilgisayar',
        }
        
        # Türkçe karakterlerin Latin karşılıkları
        self.turkish_char_map = {
            'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
            'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
        }
    
    def normalize_turkish(self, text: str) -> str:
        """Türkçe karakterleri normalize eder."""
        text = unicodedata.normalize('NFKC', text)
        return text.lower().strip()
    
    def to_latin(self, text: str) -> str:
        """Türkçe karakterleri Latin karakterlere çevirir."""
        for turkish, latin in self.turkish_char_map.items():
            text = text.replace(turkish, latin)
        return text
    
    def clean_query(self, query: str) -> str:
        """Query'yi temizler ve normalize eder."""
        # HTML entities ve özel karakterleri temizle
        query = re.sub(r'&[a-zA-Z0-9#]+;', ' ', query)
        # Fazla boşlukları temizle
        query = re.sub(r'\s+', ' ', query)
        # Başındaki ve sonundaki boşlukları kaldır
        query = query.strip()
        return query
    
    def similarity(self, a: str, b: str) -> float:
        """İki string arasındaki benzerliği hesaplar."""
        return SequenceMatcher(None, a, b).ratio()
    
    def find_best_match(self, word: str, candidates: Set[str], threshold: float = 0.6) -> Optional[str]:
        """Verilen kelime için en iyi eşleşmeyi bulur."""
        word = word.lower()
        best_match = None
        best_score = threshold
        
        for candidate in candidates:
            score = self.similarity(word, candidate)
            if score > best_score:
                best_match = candidate
                best_score = score
            
            # Latin karakterlerle de dene
            latin_word = self.to_latin(word)
            latin_candidate = self.to_latin(candidate)
            score_latin = self.similarity(latin_word, latin_candidate)
            if score_latin > best_score:
                best_match = candidate
                best_score = score_latin
        
        return best_match
    
    def correct_word(self, word: str) -> str:
        """Tek bir kelimeyi düzeltir."""
        word = self.normalize_turkish(word)
        
        # Önce direkt corrections'ta bak
        if word in self.corrections:
            return self.corrections[word]
        
        # Dictionary'de tam eşleşme var mı?
        if word in self.dictionary:
            return word
        
        # Benzer kelime bul
        best_match = self.find_best_match(word, self.dictionary)
        if best_match:
            return best_match
        
        # Değişiklik yapılamadı, orijinalini döndür
        return word
    
    def correct_query(self, query: str) -> Dict[str, any]:
        """
        Tüm query'yi düzeltir ve detaylı sonuç döndürür.
        
        Returns:
        {
            'original': 'orijinal query',
            'corrected': 'düzeltilmiş query', 
            'corrections': [{'original': 'kelime', 'corrected': 'düzeltilmiş'}],
            'confidence': 0.85
        }
        """
        original_query = query
        query = self.clean_query(query)
        
        if not query:
            return {
                'original': original_query,
                'corrected': '',
                'corrections': [],
                'confidence': 0.0
            }
        
        # Kelimelere ayır
        words = re.findall(r'\b\w+\b', query)
        corrected_words = []
        corrections_made = []
        
        for word in words:
            if len(word) < 2:  # Çok kısa kelimeler için düzeltme yapma
                corrected_words.append(word)
                continue
                
            corrected = self.correct_word(word)
            corrected_words.append(corrected)
            
            if corrected.lower() != word.lower():
                corrections_made.append({
                    'original': word,
                    'corrected': corrected,
                    'position': len(corrected_words) - 1
                })
        
        corrected_query = ' '.join(corrected_words)
        
        # Confidence hesapla
        if not corrections_made:
            confidence = 1.0
        else:
            # Her düzeltme için benzerlik skorunu hesapla
            total_similarity = sum(
                self.similarity(corr['original'], corr['corrected']) 
                for corr in corrections_made
            )
            confidence = total_similarity / len(corrections_made) if corrections_made else 1.0
        
        return {
            'original': original_query,
            'corrected': corrected_query,
            'corrections': corrections_made,
            'confidence': confidence
        }
    
    def suggest_alternatives(self, query: str, limit: int = 5) -> List[str]:
        """Query için alternatif öneriler sunar."""
        words = re.findall(r'\b\w+\b', query.lower())
        alternatives = set()
        
        for word in words:
            # Her kelime için benzer kelimeleri bul
            candidates = []
            for dict_word in self.dictionary:
                similarity = self.similarity(word, dict_word)
                if 0.3 < similarity < 0.9:  # Çok benzeri veya çok farklısı olmasın
                    candidates.append((dict_word, similarity))
            
            # En benzer 3'ünü al
            candidates.sort(key=lambda x: x[1], reverse=True)
            for candidate, _ in candidates[:3]:
                new_query = query.lower()
                new_query = re.sub(r'\b' + re.escape(word) + r'\b', candidate, new_query)
                alternatives.add(new_query)
        
        return list(alternatives)[:limit]


def main():
    """Test fonksiyonu"""
    checker = TurkishSpellChecker()
    
    # Test örnekleri
    test_queries = [
        "kozmetık ürünleri",
        "erkek gıyım",
        "siyah ayakabı",
        "bilgisaar oyun",
        "telefon kılıfı",
        "kadın elbıse",
        "cocuk ayakkabı",
        "kırmzı çanta",
        "mavı jean pantolon",
        "spor shoes",
        "computer mouse",
        "yeşıl tişort"
    ]
    
    print("🔍 Türkçe Spell Checker Test Sonuçları\n")
    print("=" * 60)
    
    for query in test_queries:
        result = checker.correct_query(query)
        print(f"\n📝 Orijinal: '{result['original']}'")
        print(f"✅ Düzeltilmiş: '{result['corrected']}'")
        print(f"🎯 Güven: {result['confidence']:.2f}")
        
        if result['corrections']:
            print("🔧 Yapılan düzeltmeler:")
            for correction in result['corrections']:
                print(f"   '{correction['original']}' → '{correction['corrected']}'")
        
        # Alternatif önerileri göster
        alternatives = checker.suggest_alternatives(query)
        if alternatives:
            print("💡 Alternatif öneriler:")
            for alt in alternatives[:3]:
                print(f"   • {alt}")
    
    print("\n" + "=" * 60)
    print("✨ Test tamamlandı!")


if __name__ == "__main__":
    main()