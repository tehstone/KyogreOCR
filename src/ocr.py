import cv2
import numpy
import pytesseract
import re
import requests
import time
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from io import BytesIO
from PIL import Image
from PIL import ImageFilter


_boss_list = ['geodude', 'snorunt', 'beldum', 'shinx', 'klink', 'alolan exeggutor',
'sneasel', 'mawile', 'lileep', 'anorith', 'alolan raichu', 'aerodactyl',
'shuckle', 'piloswine', 'skarmory', 'alolan marowak', 'lapras', 'aggron',
'absol', 'walrein', 'regirock', 'regice', 'registeel', 'mewtwo', 'exeggutor',
'raichu', 'marowak']
# Need to import base attack and stamina and  calculate these
# Raid CP Formula: ((attack+15)*math.sqrt(defense+15)*math.sqrt(stamina))/10
"""
Raid Level    Stamina
Level 1    600
Level 2    1800
Level 3    3600
Level 4    9000
Level 5    15000
Level 6    22500 * NEED TO CONFIRM - this was back calculated from formula above with Darkrai's CP
"""
raid_cp_chart = {"2873": "Shinx",
                 "3113": "Squirtle",
                 "3151": "Drifloon",
                 "3334": "Charmander",
                 "3656": "Bulbasaur",
                 "2596": "Patrat",
                 "3227": "Klink",
                 "13472": "Alolan Exeggutor",
                 "10038": "Misdreavus",
                 "10981": "Sneasel",
                 "8132": "Sableye",
                 "9008": "Mawile",
                 "5825": "Yamask",
                 "15324": "Sharpedo",
                 "16848": "Alolan Raichu",
                 "19707": "Machamp",
                 "21207": "Gengar",
                 "16457": "Granbull",
                 "14546": "Piloswine",
                 "14476": "Skuntank",
                 "21385": "Alolan Marowak",
                 "21360": "Umbreon",
                 "38490": "Dragonite",
                 "65675": "Tyranitar",
                 "20453": "Togetic",
                 "28590": "Houndoom",
                 "28769": "Absol",
                 "38326": "Altered Giratina",
                 "65675": "Darkrai"
                 }
raid_cp_list = raid_cp_chart.keys()

def get_match(word_list: list, word: str, score_cutoff: int = 60, isPartial: bool = False, limit: int = 1):
    """Uses fuzzywuzzy to see if word is close to entries in word_list

    Returns a tuple of (MATCH, SCORE)
    """
    
    if not word:
        return (None, None)
    try:
        result = None
        scorer = fuzz.ratio
        if isPartial:
            scorer = fuzz.partial_ratio
    
        if limit == 1:
            result = process.extractOne(word, word_list,
                                        scorer=scorer, score_cutoff=score_cutoff)
        else:
            result = process.extractBests(word, word_list,
                                          scorer=scorer, score_cutoff=score_cutoff, limit=limit)
    except (TypeError, AttributeError) as e:
        pass
    if not result:
        return (None, None)
    return result


def check_match(image, regex):
    img_text = pytesseract.image_to_string(image, lang='eng', config='--psm 6 -c tessedit_char_whitelist=:0123456789')
    match = re.search(regex, img_text)
    if match:
        return match.group(0)
    else:
        return None


def check_val_range(egg_time_crop, vals, regex=None, blur=False):
    for i in vals:
        thresh = cv2.threshold(egg_time_crop, i, 255, cv2.THRESH_BINARY)[1]
        if blur:
            thresh = cv2.GaussianBlur(thresh, (5, 5), 0)
        match = check_match(thresh, regex)
        if match:
            return match
    return None


def check_phone_time(image):
    height, width = image.shape
    maxy = round(height * .15)
    miny = 0
    maxx = width
    minx = 0
    phone_time_crop = image[miny:maxy, minx:maxx]
    regex = r'1{0,1}[0-9]{1}:[0-5]{1}[0-9]{1}'
    vals = [0, 10, 20]
    ivals= [40, 50, 60, 0, 10, 20]
    result = check_val_range(phone_time_crop, vals, regex, blur=True)
    if not result:
        phone_time_crop = cv2.bitwise_not(phone_time_crop)
        result = check_val_range(phone_time_crop, ivals, regex, blur=True)
    return result


def check_egg_time(image):
    image = cv2.bitwise_not(image)
    height, width = image.shape
    maxy = round(height * .33)
    miny = round(height * .16)
    maxx = round(width * .75)
    minx = round(width * .25)
    egg_time_crop = image[miny:maxy, minx:maxx]
    regex = r'[0-1]{0,1}:[0-5]{1}[0-9]{1}:[0-5]{1}[0-9]{1}'
    result = check_val_range(egg_time_crop, [0, 70, 10, 20, 80], regex)
    return result


def check_egg_tier(image):
    height, width = image.shape
    maxy = round(height * .37)
    miny = round(height * .27)
    maxx = round(width * .78)
    minx = round(width * .22)
    gym_name_crop = image[miny:maxy, minx:maxx]
    vals = [251, 252]
    for th in vals:
        thresh = cv2.threshold(gym_name_crop, th, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.GaussianBlur(thresh, (5, 5), 0)
        img_text = pytesseract.image_to_string(thresh,
                                               lang='eng', config='--psm 7 --oem 0 -c tessedit_char_whitelist=@Q®© '
                                                                  '--tessdata-dir "/usr/local/share/tessdata/"')
        tier = img_text.replace(' ', '')
        if len(tier) > 0:
            return str(len(tier))
    return None


def check_expire_time(image):
    image = cv2.bitwise_not(image)
    height, width = image.shape
    maxy = round(height * .64)
    miny = round(height * .52)
    maxx = round(width * .96)
    minx = round(width * .7)
    expire_time_crop = image[miny:maxy, minx:maxx]
    regex = r'[0-2]{0,1}:[0-5]{1}[0-9]{1}:[0-5]{1}[0-9]{1}'
    result = check_val_range(expire_time_crop, [0, 70, 10], regex)
    return result


def check_profile_name(image):
    height, width, __ = image.shape
    regex = r'\S{5,20}\n+&'
    vals = [180, 190]
    maxx = round(width * .56)
    minx = round(width * .05)
    yvals = [(.13, .24), (.2, .4)]
    for pair in yvals:
        maxy = round(height * pair[1])
        miny = round(height * pair[0])
        profile_name_crop = image[miny:maxy, minx:maxx]
        for i in vals:
            thresh = cv2.threshold(profile_name_crop, i, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.GaussianBlur(thresh, (5, 5), 0)
            img_text = pytesseract.image_to_string(thresh, lang='eng', config='--psm 4')
            match = re.search(regex, img_text)
            if match:
                return match.group(0).split('&')[0].strip()


def determine_team(image):
    b, g, r = image[300, 5]
    if r >= 200 and g >= 200:
        return "instinct"
    if b >= 200:
        return "mystic"
    if r >= 200:
        return "valor"
    return None


def check_profile_level(image):
    height, width, __ = image.shape
    vals = [220, 230, 240]
    regex = r'[1-4]{0,1}[0-9]{1}'
    maxx = round(width * .2)
    minx = round(width * .05)
    yvals = [(.5, .7), (.6, .8)]
    for pair in yvals:
        maxy = round(height * pair[1])
        miny = round(height * pair[0])
        level_crop = image[miny:maxy, minx:maxx]
        for i in vals:
            thresh = cv2.threshold(level_crop, i, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.GaussianBlur(thresh, (5, 5), 0)
            img_text = pytesseract.image_to_string(thresh, lang='eng', config='--psm 4')
            match = re.search(regex, img_text)
            if match:
                return match.group(0)


def get_xp(image):
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = image.shape
    maxy = round(height * .78)
    miny = round(height * .55)
    maxx = round(width * .96)
    minx = round(width * .55)
    xp_crop = image[miny:maxy, minx:maxx]
    vals = [210, 220]
    regex = r'[0-9,\.]{3,9}/*\s*[0-9,\.]{3,12}'
    for t in vals:
        thresh = cv2.threshold(xp_crop, t, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.GaussianBlur(thresh, (5, 5), 0)
        img_text = pytesseract.image_to_string(thresh, lang='eng', config='--psm 4')
        match = re.search(regex, img_text)
        if match:
            xp_str = match.group(0)
            if '/' in xp_str:
                return xp_str.split('/')[0].strip().replace(',', '').replace('.', '')
            else:
                return xp_str.split(' ')[0].strip().replace(',', '').replace('.', '')


def check_gym_name(image):
    height, width = image.shape
    maxy = round(height * .19)
    miny = round(height * .04)
    maxx = round(width * .92)
    minx = round(width * .15)
    gym_name_crop = image[miny:maxy, minx:maxx]
    vals = [220, 210, 190]
    possible_names = []
    for i in vals:
        thresh = cv2.threshold(gym_name_crop, i, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.GaussianBlur(thresh, (5, 5), 0)
        img_text = pytesseract.image_to_string(thresh, lang='eng', config='--psm 4')
        img_text = [s for s in list(filter(None, img_text.split('\n'))) if len(s) > 3]
        possible_text = []
        for line in img_text:
            if 'EXRAID' in line or 'EX RAID' in line:
                continue
            if len(line) < 5:
                continue
            if _word_length(line) < 4:
                continue
            line = _remove_trailings(line)
            possible_text.append(line)
        possible_names.append(' '.join(possible_text))
    return possible_names


def sub(m):
    s = {'o', 'os', 'oS', 'So', 'S', 'C', 'CS', 'O', ' )', 'Q'}
    return '' if m.group() in s else m.group()


def _remove_trailings(line):
    return re.sub(r'\w+', sub, line)


def _word_length(line):
    longest = 0
    for word in line.split():
        longest = max(longest, len(word))
    return longest


def check_boss_cp_wrap(pil_image):
    image = cv2.cvtColor(numpy.array(pil_image), cv2.COLOR_RGB2GRAY)
    boss = check_boss_cp(image)
    if not boss:
        boss = "No Match"
    return {'boss': boss}

def check_boss_cp(image, boss_list, boss_cp_map):
    height, width = image.shape
    maxy = round(height * .34)
    miny = round(height * .15)
    maxx = round(width * .89)
    minx = round(width * .11)
    gym_name_crop = image[miny:maxy, minx:maxx]
    gym_name_crop = cv2.bitwise_not(gym_name_crop)
    vals = [30, 40, 20, 50, 20, 60, 10, 70, 80]
    i_vals = [220, 252, 240, 230]
    scanned_values = []
    result, scanned_values = check_boss_internal(gym_name_crop, vals, boss_list, boss_cp_map)
    if not result:
        gym_name_crop = cv2.bitwise_not(gym_name_crop)
        result, new_scanned_values = check_boss_internal(gym_name_crop, i_vals, boss_list, boss_cp_map)
        scanned_values += new_scanned_values
    return result, scanned_values
    

def check_boss_internal(gym_name_crop, vals, boss_list, boss_cp_map):
    # This doesn't fully handle Alolan forms
    # For example, in one particular screenshot of an Alolan Marowak no boss was ever identified.
    # The img_text contained 'Marowak' but fuzzy match threshold was too high for that to match
    # Cut off can't be lower or else other issues arise (houndoom instead of absol for example)
    # Additionally, no match was ever made on the CP value as it never got a clear read.
    # Likely need to refactor this so that if an alolan species is read in, additional scans are made
    # To try and pick up the CP and make sure we have the right form
    boss_cp_list = boss_cp_map.keys()
    possible_text = []
    for t in vals:
        thresh = cv2.threshold(gym_name_crop, t, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.GaussianBlur(thresh, (5, 5), 0)
        img_text = pytesseract.image_to_string(thresh, lang='eng', config='--psm 4')
        img_text = [s for s in list(filter(None, img_text.split())) if len(s) > 3]
        possible_text.append(img_text)
        if len(img_text) > 1:
            match = get_match(boss_list, img_text[1], score_cutoff=70)
            if match and match[0]:
                return match[0], possible_text
        if len(img_text) > 0:
            match = get_match(list(boss_cp_list), img_text[0], score_cutoff=70)
            if match and match[0]:
                return boss_cp_map[match[0]], possible_text
        for i in img_text:
            match = get_match(boss_list, i, score_cutoff=70)
            if match and match[0]:
                return match[0], possible_text
            match = get_match(list(boss_cp_list), i, score_cutoff=70)
            if match and match[0]:
                return boss_cp_map[match[0]], possible_text
    return None, possible_text


def check_gym_ex(pil_image):
    image = cv2.cvtColor(numpy.array(pil_image), cv2.COLOR_RGB2GRAY)
    height, width = image.shape
    if height < 400 or width < 200:
        #print(f"height: {height} - width: {width}")
        dim = (round(width*2), round(height*2))
        image = cv2.resize(image, dim, interpolation=cv2.INTER_AREA)
    height, width = image.shape
    maxy = round(height * .38)
    miny = round(height * .19)
    maxx = round(width * .87)
    minx = round(width * .13)
    gym_name_crop = image[miny:maxy, minx:maxx]
    vals = [180, 190, 200, 210]
    result = {'date': None, 'gym': None, 'location': None}
    regex = r'(?P<date>[A-Za-z]{3,10} [0-9]{1,2} [0-9]{1,2}:[0-9]{1,2}\s*[APM]{2}\s*[-—]*\s*[0-9]{1,2}:[0-9]{1,' \
            r'2}\s*[APM]{2})\s+(?P<gym>[\S+ ]+)\s*(?P<location>[A-Za-z ]+[,\.]+ [A-Za-z]+[,\.]+ [A-Za-z ]+) '
    for i in vals:
        thresh = cv2.threshold(gym_name_crop, i, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.GaussianBlur(thresh, (5, 5), 0)
        img_text = pytesseract.image_to_string(thresh, lang='eng', config='--psm 4')
        regex_result = re.search(regex, img_text)
        if regex_result:
            results = regex_result.groupdict()
            result['date'] = results['date']
            result['gym'] = results['gym']
            result['location'] = results['location']
            break
    return result


def scan_raid_photo(pil_image, boss_list, boss_cp_map):
    start = time.time()
    image = cv2.cvtColor(numpy.array(pil_image), cv2.COLOR_RGB2GRAY)
    height, width = image.shape
    if height < 400 or width < 200:
        dim = (round(width * 2), round(height * 2))
        image = cv2.resize(image, dim, interpolation=cv2.INTER_AREA)
    result_gym = check_gym_name(image)
    result_egg, result_expire, result_boss, result_tier, result_phone, scanned_values = None, None, None, None, None, []
    # If we don't have a gym, no point in checking anything else
    if result_gym:
        result_egg = check_egg_time(image)
        # Only check for expire time and boss if no egg time found
        # May make sense to reverse this. Tough call.
        if not result_egg:
            result_boss, scanned_values = check_boss_cp(image, boss_list, boss_cp_map)
            result_expire = check_expire_time(image)
        if result_egg or result_expire:
            try:
                boss = False
                if result_expire:
                    boss = True
                result_tier = check_egg_tier(image, boss)
            except Exception as e:
                #logger.info(f"Could not read egg tier from text. Error: {e}")
                # TODO return error
                pass
        # If we don't find an egg time or a boss, we don't need the phone's time
        # Even if it's picked up as an egg later, the time won't be correct without egg time
        if result_egg or result_boss or result_tier:
            result_phone = check_phone_time(image)
    result = {'egg_time': result_egg, 'expire_time': result_expire, 'boss': result_boss, 's_tier': result_tier,
            'phone_time': result_phone, 'names': result_gym, 'runtime': time.time() - start, 'boss_scans': scanned_values}
    print(result)
    return result


def scan_profile(pil_image):
    image = cv2.cvtColor(numpy.array(pil_image), cv2.COLOR_RGB2BGR)
    height, width, __ = image.shape
    if height < 400 or width < 200:
        #print(f"height: {height} - width: {width}")
        dim = (round(width*2), round(height*2))
        image = cv2.resize(image, dim, interpolation=cv2.INTER_AREA)
    team = determine_team(image)
    if team == 'grey':
        return None, None, None, None
    level = check_profile_level(image)
    trainer_name = check_profile_name(image)
    xp = None
    if level:
        try:
            lev_int = int(level)
            if lev_int < 40:
                xp = get_xp(image)
        except ValueError:
            pass
    return {"team ": team , "level": level, "trainer_name": trainer_name, "xp": xp}


def process_image(url, scan_type, boss_list, boss_cp_map):
    image = _get_image(url)
    #image.filter(ImageFilter.SHARPEN)
    if scan_type == "expass":
        return check_gym_ex(image)
    if scan_type == "raid":
        return scan_raid_photo(image, boss_list, boss_cp_map)
    if scan_type == "profile":
        return scan_profile(image)
    if scan_type == "boss":
        return check_boss_cp_wrap(image)



def _get_image(url):
    return Image.open(BytesIO(requests.get(url).content))
