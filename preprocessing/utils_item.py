from matplotlib.colors import hex2color
import openpyxl
import colorgram
import requests
import webcolors
import warnings
import json
import re

import pandas as pd

from rembg import remove
from PIL import Image
from io import BytesIO
from tqdm import tqdm
from typing import List, Tuple, Union

warnings.filterwarnings(action='ignore')


#########################
#        COLOR          #
#########################
# 이미지를 불러오는 함수
def get_img_from_url(url: str) -> Image:
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    return img


# 이미지에 포함된 상위 K개의 색상 가져오기
def topK_colors(img: Image, k: int) -> List:
    colors = colorgram.extract(img, k)
    # print (colors)
    rgb_lists = list()

    for idx in range(k):
        if idx == len(colors):
            break
        R = colors[idx].rgb.r
        G = colors[idx].rgb.g
        B = colors[idx].rgb.b
        rgb_lists.append([R, G, B])

    return rgb_lists


def color_preprocess(item_df: pd.DataFrame) -> pd.DataFrame:

    color_r = list()
    color_g = list()
    color_b = list()

    # 이미지에서 색 추출 과정s
    for img_url in tqdm(item_df['img_url']):
        try:
            img = get_img_from_url(img_url)
        except:
            color_r.append("0")
            color_g.append("0")
            color_b.append("0")
            continue

        img = img.resize((240, 320))        # 이미지 크기 조정 (속도 향상)
        img = remove(img)                   # 배경제거
        color_list = topK_colors(img, 5)    # 이미지에 포함된 상위 K 개의 색 추출
     
        # R, G, B 값 가져오기
        R, G, B = color_list[1]
        color_r.append(R)
        color_g.append(G)
        color_b.append(B)
        

    #-- 이미지에서 선택된 hex 코드를 색상 이름으로 변경
    item_df['R'] = color_r
    item_df['G'] = color_g
    item_df['B'] = color_b
    # item_df['color_name'] = item_df['hex_color'].apply(lambda x: hex2color[x])
    item_df.to_excel('./temp_preprocess_color.xlsx', engine='openpyxl', index=False)

    print ("Preprocessing Color Done..")

    return item_df










# 평점 결측치 처리
def rating_preprocess(item_df: pd.DataFrame) -> pd.DataFrame:
    avg_rating = item_df[item_df['rating'].notnull()]['rating'].mean()
    item_df['rating'] = item_df['rating'].fillna(avg_rating)
    return item_df







def class_preprocess(raw_item_data) :

    base_big_class = ['아우터', '상의', '바지', '가방', '신발', '모자']
    df = raw_item_data[["id", "big_class", "mid_class"]]

    # 전처리 
    for mid_class in ['캔버스/단화', '패션스니커즈화', '기타 스니커즈', '농구화'] :
        df.loc[df["mid_class"]==mid_class, "big_class"] = "신발"

    for mid_class in ['안경', '선글라스', '양말', '팔찌', '반지', '목걸이/펜던트', '발찌', '스포츠잡화', '디지털', '쿼츠 아날로그', '오토매틱 아날로그', '카메라/카메라용품', '우산'] :
        df.loc[df["mid_class"]==mid_class, "big_class"] = "액세서리"

    df.loc[df["mid_class"]=="스포츠신발", "big_class"] = "신발"

    for mid_class in ["스포츠가방",'백팩', '크로스백'] :
        df.loc[df["mid_class"]==mid_class, "big_class"] = "가방"

    # 전처리한 대분류, 중분류 원 데이터에 반영
    raw_item_data["big_class"] = df["big_class"]
    raw_item_data["mid_class"] = df["mid_class"]

    # 액세서리, 속옷 대분류 제거 
    accessory_index = raw_item_data[raw_item_data["big_class"]=="액세서리"].index
    underwear_index = raw_item_data[raw_item_data["big_class"]=="속옷"].index
    raw_item_data.drop(accessory_index, inplace=True)
    raw_item_data.drop(underwear_index, inplace=True)

    # 출력 엑셀의 형식을 원래 데이터의 형식과 동일하게 맞춰주기 위한 부분
    raw_item_data["id"] = raw_item_data["id"].apply(str)

    # 한번도 보지 못한 대분류 아이템 제거
    unique_big_class = list(raw_item_data["big_class"].unique())
    new_big_class = list(set(unique_big_class) - set(base_big_class))

    need_revision_total_df = pd.DataFrame([], columns=list(raw_item_data.columns))
    for new_class in new_big_class :
        need_revision_df = raw_item_data.loc[raw_item_data["big_class"]==new_class]
        need_revision_total_df = pd.concat([need_revision_total_df, need_revision_df])

        left_out_index = need_revision_df.index
        raw_item_data.drop(left_out_index, inplace=True)

    need_revision_total_df["revision"] = ["big_class"] * len(need_revision_total_df)

    return raw_item_data, need_revision_total_df




# 좋아요 수 전처리
def likes_preprocess(raw_data: pd.DataFrame) -> pd.DataFrame:

    raw_data["likes"] = raw_data["likes"].fillna(0)
    return raw_data



# 성별 전처리
def gender_preprocess(raw_data: pd.DataFrame) -> pd.DataFrame:

    def preprocessing_gender_info(gender_info):
        '''
        성병 정보 추출 및 변환
        : gender_info - 하나의 아이템에 대한 gener 정보 (str or nan)
        '''
        if type(gender_info) == str:
            if gender_info == '남 여': return '유니섹스'
            return gender_info
        return gender_info # TODO: 성별 정보가 없을 때!

    # -- gender 데이터 전처리
    raw_data['gender'] = raw_data.gender.transform(preprocessing_gender_info)
    return raw_data


def season_preprocess(raw_data: pd.DataFrame) -> pd.DataFrame:

    def make_season_day(season_info):
        '''
        season 정보를 사용하여 season day 추출 및 생성
        : season_info - 하나의 item에 대한 season 정보 (str or nan)
        '''
        if type(season_info) == str:
            day = re.search('[0-9]{4}', season_info)
            if day: return int(day.group())
        return None

    

    def preprosessing_season_info(season_info):
        '''
        season_info에서 S/S, F/W, ALL 정보 추출 및 변환
        : season_info - 하나의 item에 대한 season 정보 (str or nan)
        '''
        if type(season_info) == str:
            if re.search('[A-Z]\/[A-Z]', season_info): # S/S format의 str이 있는 경우 해당 정보를 뽑아냄
                return re.search('[A-Z]\/[A-Z]', season_info).group()
            elif re.search('[A-Z]{3}', season_info):   # ALL인 경우 해당 정보를 뽑아냄
                return re.search('[A-Z]{3}', season_info).group()
        return None

    # -- season_day feature 생성
    raw_data['season_day'] = raw_data.season.transform(make_season_day)

    # -- season 데이터 전처리
    raw_data['season'] = raw_data.season.transform(preprosessing_season_info)

    return raw_data

def buy_age_preprocess(item_data : pd.DataFrame) -> pd.DataFrame :
    
    buy_age_data = pd.read_excel("/opt/ml/input/data/raw_codishop/view/item/item_buy_age.xlsx")

    most_bought_age_dict = dict()
    for i in range(len(buy_age_data)) :
        user_id = buy_age_data["id"].iloc[i]
        user_data = buy_age_data.iloc[i].drop("id")
        index = user_data.argmax()
        most_bought_age_dict[user_id] = index

    most_bought_age_list = list()
    for user in item_data["id"] :
        try :
            most_bought_age_list.append(most_bought_age_dict[user])
        except :
            most_bought_age_list.append(6)

    item_data["most_bought_age_class"] = most_bought_age_list

    return item_data