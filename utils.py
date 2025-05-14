def parse_user_input(user_input):
    try:
        lines = [line.strip() for line in user_input.split("\n") if line.strip()]
        preferences = {
            'shape': None,
            'carat': None,
            'color': None,
            'clarity': None,
            # 'cut': None
        }

        for line in lines:
            line_lower = line.lower()

            if any(shape in line_lower for shape in ['round', 'oval', 'cushion', 'emerald', 'princess', 'pear', 'marquise']):
                preferences['shape'] = line_lower.capitalize()

            elif "ct" in line_lower or "carat" in line_lower:
                carat_value = line_lower.replace("carat", "").replace("ct", "").strip()
                preferences['carat'] = float(carat_value)

            elif "color" in line_lower or line_lower in ['d', 'e', 'f', 'g', 'h']:
                preferences['color'] = line_lower.replace("color", "").strip().upper()

            elif any(c in line_lower for c in ['vs1', 'vs2', 'vvs1', 'vvs2', 'si1', 'si2']):
                preferences['clarity'] = line_lower.upper()

            # elif any(cut in line_lower for cut in ['ideal', 'excellent', 'very good', 'good']):
            #     preferences['cut'] = line_lower.capitalize()

        if all(preferences.values()):
            return preferences
        else:
            return None

    except Exception as e:
        print(f"Parsing error: {e}")
        return None
