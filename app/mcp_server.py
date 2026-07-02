from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AyushMitra")

# Rich Mock Databases
HOSPITALS_DB = [
    {
        "name": "All India Institute of Medical Sciences (AIIMS)",
        "state": "Delhi",
        "city": "New Delhi",
        "specialties": ["cardiology", "oncology", "neurology", "general"],
        "contact": "011-26588500"
    },
    {
        "name": "Sanjay Gandhi Postgraduate Institute of Medical Sciences (SGPGI)",
        "state": "Uttar Pradesh",
        "city": "Lucknow",
        "specialties": ["gastroenterology", "cardiology", "nephrology", "general"],
        "contact": "0522-2668700"
    },
    {
        "name": "Tata Memorial Hospital",
        "state": "Maharashtra",
        "city": "Mumbai",
        "specialties": ["oncology", "radiotherapy"],
        "contact": "022-24177000"
    },
    {
        "name": "Government General Hospital",
        "state": "Tamil Nadu",
        "city": "Chennai",
        "specialties": ["general", "pediatrics", "orthopedics"],
        "contact": "044-25305000"
    },
    {
        "name": "King George Hospital",
        "state": "Andhra Pradesh",
        "city": "Visakhapatnam",
        "specialties": ["general", "cardiology", "neurology"],
        "contact": "0891-2564891"
    },
    {
        "name": "Medanta The Medicity",
        "state": "Haryana",
        "city": "Gurugram",
        "specialties": ["cardiology", "neurology", "orthopedics"],
        "contact": "0124-4141414"
    }
]

MEDICAL_SHORTHAND = {
    "tid": "Three times a day (दिन में तीन बार, सुबह-दोपहर-शाम)",
    "bid": "Twice a day (दिन में दो बार, सुबह और शाम)",
    "qid": "Four times a day (दिन में चार बार)",
    "qd": "Once a day (दिन में एक बार)",
    "prn": "As needed or in case of pain/emergency (ज़रूरत पड़ने पर या दर्द होने पर)",
    "ac": "Before meals / Empty stomach (खाली पेट / खाने से पहले)",
    "pc": "After meals (खाना खाने के बाद)",
    "po": "By mouth (मुंह से पानी के साथ निगलें)",
    "pcm": "Paracetamol / Crocin (बुखार और बदन दर्द के लिए)",
    "amx": "Amoxicillin (एंटीबायोटिक - संक्रमण के लिए)",
    "hs": "At bedtime (रात को सोते समय)",
    "od": "Once a day (दिन में एक बार)"
}

PHARMACIES_DB = [
    {"name": "Jan Aushadhi Kendra - Connaught Place", "city": "New Delhi", "address": "Shop 4, Block A, Connaught Place", "contact": "+91-9876543210"},
    {"name": "Jan Aushadhi Kendra - Hazratganj", "city": "Lucknow", "address": "12, Mahatma Gandhi Marg, Hazratganj", "contact": "+91-9876543211"},
    {"name": "Jan Aushadhi Kendra Dadar", "city": "Mumbai", "address": "Opposite Dadar West Railway Station", "contact": "+91-9876543212"},
    {"name": "Jan Aushadhi Kendra - T. Nagar", "city": "Chennai", "address": "45, Usman Road, T. Nagar", "contact": "+91-9876543213"}
]

@mcp.tool()
def search_hospitals(location: str, specialty: str = None) -> str:
    """Search for Ayushman Bharat PM-JAY empanelled hospitals in India.

    Args:
        location: City, district, or region in India (e.g. 'Mumbai', 'Lucknow', 'Delhi').
        specialty: Medical specialty needed (e.g. 'cardiology', 'oncology', 'general').
    """
    loc_clean = location.lower().strip()
    spec_clean = specialty.lower().strip() if specialty else None
    
    matches = []
    for h in HOSPITALS_DB:
        # Match city or state
        if loc_clean in h["city"].lower() or loc_clean in h["state"].lower():
            if not spec_clean or any(spec_clean in s for s in h["specialties"]):
                matches.append(h)
                
    if not matches:
        return f"No Ayushman Bharat empaneled hospitals found matching location '{location}' and specialty '{specialty or 'Any'}'. Please try general searches."
        
    res = f"Found {len(matches)} Ayushman Bharat empaneled hospital(s):\n"
    for i, h in enumerate(matches, 1):
        specs_str = ", ".join(h["specialties"]).title()
        res += f"{i}. {h['name']} ({h['city']}, {h['state']})\n   - Specialties: {specs_str}\n   - Contact: {h['contact']}\n"
    return res

@mcp.tool()
def check_eligibility(income: float, state: str = "Any") -> str:
    """Check if a household is eligible for the Ayushman Bharat PM-JAY health card.

    Args:
        income: Annual household income in INR.
        state: State of residence in India (default: 'Any').
    """
    # General PM-JAY limit (deprived households, SECC criteria, or income < 250,000 INR depending on state)
    if income <= 250000:
        return (
            f"✅ Eligible. Based on the annual income of ₹{income:,} in {state}, "
            "your household meets the financial criteria for the Ayushman Bharat PM-JAY health cover (₹5 Lakh free treatment/year)."
        )
    else:
        return (
            f"❌ Not Eligible under standard income criteria. The annual income of ₹{income:,} exceeds the standard "
            "PM-JAY limit (typically ₹2,50,000 for low-income state criteria). However, you may still check if your family "
            "is listed in the SECC 2011 database or has a BPL/Ration card."
        )

@mcp.tool()
def simplify_terms(text: str) -> str:
    """Translate and simplify complex medical terms, prescription shorthand, or drug abbreviations.

    Args:
        text: Medical terms or instructions (e.g., 'TID', 'PCM ac', 'BID pc').
    """
    words = text.lower().replace(",", " ").replace(".", " ").split()
    translated = []
    
    for w in words:
        if w in MEDICAL_SHORTHAND:
            translated.append(f"{w.upper()}: {MEDICAL_SHORTHAND[w]}")
            
    if not translated:
        return (
            f"Could not find specific shorthand translations for '{text}' in local dictionary. "
            "Simplification recommendation: Consult a local generic pharmacy (Jan Aushadhi Kendra) for advice."
        )
        
    return "Here are the simplified terms found:\n" + "\n".join(translated)

@mcp.tool()
def find_nearest_pharmacy(city: str) -> str:
    """Find nearby Pradhan Mantri Bhartiya Janaushadhi Kendras (generic medicine stores) in the given city.

    Args:
        city: Indian city (e.g. 'Mumbai', 'Lucknow', 'Delhi').
    """
    city_clean = city.lower().strip()
    matches = [p for p in PHARMACIES_DB if city_clean in p["city"].lower()]
    
    if not matches:
        return f"No generic pharmacy locations found for city '{city}' in database. You can locate all generic stores at http://janaushadhi.gov.in"
        
    res = f"Found {len(matches)} Jan Aushadhi Kendra(s) in {city}:\n"
    for i, p in enumerate(matches, 1):
        res += f"{i}. {p['name']}\n   - Address: {p['address']}\n   - Contact: {p['contact']}\n"
    return res

if __name__ == "__main__":
    mcp.run()
