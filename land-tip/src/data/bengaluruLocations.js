// Complete 10-Category Bengaluru Location Database for UrbanAlpha
// Coordinates are provided for major hubs; any item without explicit coords
// resolves dynamically via Nominatim (Bengaluru-bounded) with zone-center fallback.

export const ZONE_CENTERS = {
  "Central Bengaluru": { coords: [12.9716, 77.5946], basePrice: 22500, cagr: 0.066, metroKm: 0.4, builtUp: 91 },
  "North Bengaluru": { coords: [13.0450, 77.5950], basePrice: 10800, cagr: 0.098, metroKm: 1.4, builtUp: 72 },
  "South Bengaluru": { coords: [12.9050, 77.5850], basePrice: 13200, cagr: 0.082, metroKm: 0.9, builtUp: 80 },
  "East Bengaluru": { coords: [12.9750, 77.6950], basePrice: 14500, cagr: 0.091, metroKm: 0.8, builtUp: 81 },
  "Southeast Bengaluru": { coords: [12.9150, 77.6550], basePrice: 14800, cagr: 0.089, metroKm: 1.5, builtUp: 82 },
  "West Bengaluru": { coords: [12.9750, 77.5350], basePrice: 11400, cagr: 0.075, metroKm: 0.7, builtUp: 84 },
  "Historical & Architectural": { coords: [12.9760, 77.5920], basePrice: 20500, cagr: 0.064, metroKm: 0.6, builtUp: 88 },
  "Parks, Lakes & Nature": { coords: [12.9580, 77.6050], basePrice: 15200, cagr: 0.078, metroKm: 1.1, builtUp: 65 },
  "Malls & Commercial": { coords: [12.9720, 77.6150], basePrice: 17800, cagr: 0.084, metroKm: 0.6, builtUp: 89 },
  "Transport Landmarks": { coords: [12.9780, 77.5720], basePrice: 15900, cagr: 0.088, metroKm: 0.2, builtUp: 87 },
  "Education & Institutions": { coords: [12.9650, 77.5850], basePrice: 14900, cagr: 0.074, metroKm: 0.9, builtUp: 82 },
  "Tech Parks & Business Hubs": { coords: [12.9450, 77.6950], basePrice: 13900, cagr: 0.095, metroKm: 1.0, builtUp: 85 },
  "Markets & Food Streets": { coords: [12.9640, 77.5800], basePrice: 18400, cagr: 0.071, metroKm: 0.5, builtUp: 92 },
  "Stadiums & Entertainment": { coords: [12.9750, 77.5990], basePrice: 19200, cagr: 0.070, metroKm: 0.5, builtUp: 87 },
  "Major Roads & Corridors": { coords: [12.9550, 77.6300], basePrice: 15600, cagr: 0.087, metroKm: 0.8, builtUp: 86 }
};

export const EXACT_COORDS = {
  "MG Road": [12.9756, 77.6066],
  "Indiranagar": [12.9784, 77.6408],
  "Whitefield": [12.9698, 77.7499],
  "Electronic City": [12.8452, 77.6602],
  "Koramangala": [12.9352, 77.6245],
  "HSR Layout": [12.9116, 77.6389],
  "Hebbal": [13.0358, 77.5970],
  "Jayanagar": [12.9308, 77.5838],
  "Yelahanka": [13.1007, 77.5963],
  "Yeshwanthpur": [13.0285, 77.5409],
  "Majestic": [12.9767, 77.5713],
  "Rajajinagar": [12.9982, 77.5530],
  "Vijayanagar": [12.9719, 77.5330],
  "Marathahalli": [12.9591, 77.6974],
  "Bellandur": [12.9260, 77.6762],
  "Sarjapur Road": [12.9100, 77.6850],
  "KR Puram": [13.0012, 77.6962],
  "JP Nagar": [12.9063, 77.5857],
  "BTM Layout": [12.9166, 77.6101],
  "Banashankari": [12.9255, 77.5468],
  "Basavanagudi": [12.9406, 77.5738],
  "Kengeri": [12.9177, 77.4838],
  "Devanahalli": [13.2473, 77.7139],
  "Vidhana Soudha": [12.9797, 77.5912],
  "Bengaluru Palace": [12.9988, 77.5921],
  "Cubbon Park": [12.9764, 77.5929],
  "Lalbagh Botanical Garden": [12.9507, 77.5848],
  "Ulsoor Lake": [12.9817, 77.6197],
  "Sankey Tank": [13.0094, 77.5736],
  "Hebbal Lake": [13.0469, 77.5877],
  "UB City": [12.9716, 77.5961],
  "Orion Mall": [13.0110, 77.5549],
  "Phoenix Marketcity": [12.9958, 77.6964],
  "Kempegowda International Airport": [13.1986, 77.7066],
  "Indian Institute of Science (IISc)": [13.0219, 77.5671],
  "IIM Bangalore": [12.8959, 77.6020],
  "Manyata Tech Park": [13.0458, 77.6203],
  "International Tech Park Bangalore (ITPB)": [12.9854, 77.7366],
  "Bagmane Tech Park": [12.9812, 77.6619],
  "Embassy GolfLinks": [12.9498, 77.6426],
  "RMZ Ecoworld": [12.9216, 77.6844],
  "M. Chinnaswamy Stadium": [12.9788, 77.5996],
  "ISKCON Temple": [13.0098, 77.5511]
};

export const BENGALURU_DATABASE = [
  {
    category: "Central Bengaluru",
    group: "Areas",
    items: [
      "MG Road", "Brigade Road", "Ashok Nagar", "Richmond Town", "Residency Road",
      "Church Street", "Commercial Street", "Shivajinagar", "Vasanth Nagar",
      "Seshadripuram", "Gandhinagar", "Majestic", "Chickpet", "KR Market",
      "Lavelle Road", "Cunningham Road", "Infantry Road", "St. Marks Road",
      "Langford Town", "Shantinagar", "Cubbon Park", "Chamarajpet"
    ]
  },
  {
    category: "North Bengaluru",
    group: "Areas",
    items: [
      "Hebbal", "Yelahanka", "Jakkur", "Thanisandra", "Nagavara", "Hennur",
      "RT Nagar", "Sanjay Nagar", "Sahakara Nagar", "Kodigehalli", "Jalahalli",
      "Vidyaranyapura", "Mathikere", "Ganganagar", "Amruthahalli", "Kogilu",
      "Bagalur", "Devanahalli", "Yeshwanthpur", "Peenya", "Dasarahalli",
      "Abbigere", "Chikkabanavara", "Hesaraghatta", "Madavara", "Soladevanahalli"
    ]
  },
  {
    category: "South Bengaluru",
    group: "Areas",
    items: [
      "Jayanagar", "JP Nagar", "Basavanagudi", "Banashankari", "Kumaraswamy Layout",
      "Padmanabhanagar", "Girinagar", "Uttarahalli", "Arekere", "Hulimavu",
      "BTM Layout", "Bommanahalli", "Begur", "Gottigere", "Konanakunte",
      "Anjanapura", "Kaggalipura", "Bannerghatta", "Electronic City",
      "Bommasandra", "Basavanapura"
    ]
  },
  {
    category: "East Bengaluru",
    group: "Areas",
    items: [
      "Indiranagar", "HAL", "Domlur", "Old Airport Road", "CV Raman Nagar",
      "Kaggadasapura", "New Thippasandra", "Jeevan Bima Nagar", "Marathahalli",
      "Brookefield", "Kundalahalli", "Whitefield", "Hoodi", "KR Puram",
      "Mahadevapura", "Varthur", "Kadugodi", "ITPL", "Ramamurthy Nagar",
      "Doddanekundi", "Bellandur", "Panathur", "Horamavu", "TC Palya"
    ]
  },
  {
    category: "Southeast Bengaluru",
    group: "Areas",
    items: [
      "Koramangala", "HSR Layout", "Sarjapur Road", "Kasavanahalli", "Haralur",
      "Kaikondrahalli", "Doddakannelli", "Carmelaram", "Kodathi", "Choodasandra",
      "Parappana Agrahara", "Devarabeesanahalli", "Kadubeesanahalli", "Iblur",
      "Marathahalli ORR", "Munnekollal"
    ]
  },
  {
    category: "West Bengaluru",
    group: "Areas",
    items: [
      "Rajajinagar", "Vijayanagar", "Nagarbhavi", "Basaveshwaranagar",
      "Kamakshipalya", "Attiguppe", "RPC Layout", "Chandra Layout",
      "Deepanjali Nagar", "Mysore Road", "Kengeri", "RR Nagar", "BEML Layout",
      "Magadi Road", "Sunkadakatte", "Annapoorneshwari Nagar", "Nandini Layout",
      "Mahalakshmi Layout", "Srirampura", "Nayandahalli", "Ullal"
    ]
  },
  {
    category: "Historical & Architectural",
    group: "Historical",
    items: [
      "Vidhana Soudha", "Bengaluru Palace", "Tipu Sultan's Summer Palace",
      "Bengaluru Fort", "Attara Kacheri (High Court)", "Bull Temple",
      "Gavi Gangadhareshwara Temple", "Dodda Ganapathi Temple", "St. Mary's Basilica",
      "Bangalore Town Hall", "Bangalore University", "National Gallery of Modern Art",
      "Visvesvaraya Industrial and Technological Museum", "Jawaharlal Nehru Planetarium",
      "Karnataka Chitrakala Parishath", "ISKCON Temple", "Infant Jesus Church"
    ]
  },
  {
    category: "Parks, Lakes & Nature",
    group: "Parks & Lakes",
    items: [
      "Cubbon Park", "Lalbagh Botanical Garden", "Ulsoor Lake", "Sankey Tank",
      "Hebbal Lake", "Kaikondrahalli Lake", "JP Park", "Bannerghatta National Park",
      "Madiwala Lake", "Agara Lake", "Puttenahalli Lake", "Jakkur Lake",
      "Nagavara Lake", "Bellandur Lake", "Varthur Lake", "Hesaraghatta Lake",
      "Turahalli Forest", "Avalahalli Forest", "Bugle Rock Park", "Freedom Park",
      "Coles Park", "Cariappa Memorial Park", "Jayamahal Park"
    ]
  },
  {
    category: "Malls & Commercial",
    group: "Malls",
    items: [
      "UB City", "Orion Mall", "Mantri Square", "Phoenix Marketcity",
      "VR Bengaluru", "Forum Koramangala", "Nexus Shantiniketan",
      "Royal Meenakshi Mall", "Gopalan Arcade Mall", "Garuda Mall",
      "Nexus Koramangala", "Nexus Whitefield", "Lulu Mall Bengaluru",
      "GT World Mall", "Esteem Mall", "Elements Mall", "1 MG-Lido Mall",
      "Central Mall Bellandur"
    ]
  },
  {
    category: "Transport Landmarks",
    group: "Transport",
    items: [
      "Kempegowda International Airport", "Kempegowda Bus Station (Majestic)",
      "KSR Bengaluru City Railway Station", "Bengaluru Cantonment Railway Station",
      "Yesvantpur Junction", "Krishnarajapuram Railway Station",
      "Baiyappanahalli Metro Interchange", "Nadaprabhu Kempegowda Metro Station",
      "Mysore Road Satellite Bus Station", "Shivajinagar Bus Station",
      "Electronic City Bus Terminal", "Yelahanka Railway Station",
      "Whitefield Railway Station", "Kengeri Railway Station",
      "Banaswadi Railway Station", "SMVT Bengaluru Railway Station",
      "Banashankari Metro Station", "Silk Institute Metro Station",
      "Yeshwanthpur Metro Station"
    ]
  },
  {
    category: "Education & Institutions",
    group: "Education",
    items: [
      "Indian Institute of Science (IISc)", "IIM Bangalore", "Christ University",
      "Bangalore University", "RV College of Engineering", "PES University",
      "NIMHANS", "BMS College of Engineering", "Ramaiah Institute of Technology",
      "Dayananda Sagar College of Engineering", "Jain University",
      "Mount Carmel College", "St. Joseph's University",
      "National Law School of India University", "Bangalore Medical College",
      "IIIT Bangalore", "Azim Premji University"
    ]
  },
  {
    category: "Tech Parks & Business Hubs",
    group: "Tech Parks",
    items: [
      "Manyata Tech Park", "International Tech Park Bangalore (ITPB)",
      "Bagmane Tech Park", "Pritech Park", "Prestige Tech Park",
      "IBC Knowledge Park", "Ecospace Business Park", "RMZ Ecoworld",
      "Embassy GolfLinks", "Global Tech Park", "Electronic City Phase 1",
      "Electronic City Phase 2", "Embassy Tech Village", "Brigade Tech Gardens",
      "Cessna Business Park", "Divyasree Technopolis", "RMZ Infinity",
      "Brigade Metropolis", "Global Village Tech Park", "Salarpuria Softzone"
    ]
  },
  {
    category: "Markets & Food Streets",
    group: "Markets",
    items: [
      "KR Market", "Russell Market", "Commercial Street", "Chickpet Market",
      "VV Puram Food Street", "Malleswaram 8th Cross", "Jayanagar 4th Block Market",
      "Gandhi Bazaar", "Shivajinagar Market", "SP Road", "Avenue Road",
      "Johnson Market", "Thippasandra Market", "Indiranagar 100 Feet Road",
      "Koramangala 5th Block"
    ]
  },
  {
    category: "Stadiums & Entertainment",
    group: "Stadiums",
    items: [
      "M. Chinnaswamy Stadium", "Kanteerava Stadium",
      "Sree Kanteerava Indoor Stadium", "Bangalore International Exhibition Centre",
      "Ranga Shankara", "Ravindra Kalakshetra", "Bangalore Palace Grounds",
      "Wonderla Amusement Park", "Innovative Film City", "Snow City",
      "Fun World", "Lalbagh Glass House"
    ]
  },
  {
    category: "Major Roads & Corridors",
    group: "Roads",
    items: [
      "Outer Ring Road (ORR)", "Old Airport Road", "Hosur Road",
      "Bannerghatta Road", "Kanakapura Road", "Mysore Road", "Tumkur Road",
      "Bellary Road", "Old Madras Road", "Sarjapur Road", "Whitefield Main Road",
      "Magadi Road", "Residency Road", "Cunningham Road", "Brigade Road",
      "100 Feet Road Indiranagar", "100 Feet Road Koramangala",
      "Electronic City Flyover", "Hebbal Flyover", "Hennur Road",
      "Thanisandra Main Road", "Varthur Road", "Marathahalli Bridge",
      "Airport Road", "Richmond Road", "Jayanagar 4th Block Main Road"
    ]
  }
];
