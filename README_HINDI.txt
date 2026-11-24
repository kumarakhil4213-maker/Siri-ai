SIRI REAL WEB APP — Moto G85 + Termux

यह स्थानीय फोन पर चलने वाला वास्तविक Gemini चैट सर्वर है। यह सार्वजनिक इंटरनेट पर होस्ट नहीं है।

जरूरी:
- आपकी Gemini API key इस फ़ोल्डर/HTML में नहीं है। सर्वर इसे ~/.config/siri/gemini.env से पढ़ता है।
- मॉडल default: gemini-flash-lite-latest (इसे environment variable SIRI_GEMINI_MODEL से बदला जा सकता है)।
- चैट के लिए इंटरनेट और वैध Gemini API key जरूरी है।
- माइक Chrome/Web Speech support और microphone permission पर निर्भर है।
- केवल 127.0.0.1 पर bind होता है, इसलिए LAN/public network पर expose नहीं होता।

Termux में:
1) ZIP को Downloads में डाउनलोड करके Extract करें। फ़ोल्डर का नाम siri_real_web रखें और उसे Termux home में रखें:
   cp -r /sdcard/Download/siri_real_web ~/siri_real_web
   (अगर Extract location अलग है तो path उसी अनुसार बदलें)

2) सुनिश्चित करें कि key पहले से सेव है:
   cat ~/.config/siri/gemini.env | sed 's/=.*/=SAVED/'
   इसमें GEMINI_API_KEY=SAVED दिखना चाहिए। असली key किसी को न भेजें।

3) चलाएँ:
   cd ~/siri_real_web
   python server.py

4) उसी फोन के Chrome में खोलें:
   http://127.0.0.1:8765

5) बंद करने के लिए Termux में Ctrl+C दबाएँ।

अगर "Address already in use" आए तो कोई पुराना SIRI सर्वर पहले से चल रहा है।
अगर API 400/403/404/429 दे तो पूरा error text देखें: key/model/access/quota issue हो सकता है।
अगर model not found आए तो Termux में चलाएँ:
   SIRI_GEMINI_MODEL=gemini-flash-lite-latest python server.py

ध्यान:
- यह अभी एक फोन पर लोकल वेब ऐप है, hosted public URL या APK नहीं।
- सेव यादें ~/siri_real_web/data/memories.json में रहती हैं।
- Browser chat history केवल वर्तमान टैब की memory में रहती है।
- Android के दूसरे ऐप खोलने, background wake word, alarms आदि के लिए native Android permissions वाला APK चाहिए।
