import requests
import json
import API_KEY
import time
import random
from bs4 import BeautifulSoup
import sqlite3
import plotly.graph_objs as go

BASE_URL_SEARCH = 'https://api.yelp.com/v3/businesses/search?'
headers = {'Authorization': 'Bearer '+ f'{API_KEY.API_key}'}
DBNAME = 'final_proj_fusion.sqlite'
conn = sqlite3.connect(DBNAME)
cur = conn.cursor()

class Business:
    '''a yelp business

    Instance Attributes
    -------------------
    id: string
        the unique yelp id of a business
    
    alias: string
        the title of a business
    
    name: string
        the string of a business
    
    url: stirng
        the url of a business
    
    review_coumt: integer
        the count of reviews of a business
    
    category_title_list: list
        the list of categories of a business

    rating: float
        the rating of a business

    price_level: integer
        the price level of a business, the higher, the more expensive, '6' means null
    
    location_zip_code: string
        the zip code of a business
    
    location_city: string
        the city of a business
    
    location_state: string
        the state of a business
    
    location_country: string
        the alpha-2 code of a country (e.g. US)
    
    location_display_address_list: list
        the list of displayed address
    
    display_phone: string
        
    '''
    def __init__(self, id, alias, name, url, review_count, 
        category_title_list, rating, price, location_zip_code, 
        location_city, location_state, location_country, 
        location_display_address, display_phone):
        self.id = id
        self.alias = alias
        self.name = name
        self.url = url
        self.review_count = review_count
        self.category_title_list = category_title_list
        self.rating = rating
        self.price_level = price
        self.location_zip_code = location_zip_code
        self.location_city = location_city
        self.location_state = location_state
        self.location_country = location_country
        self.location_display_address_list = location_display_address
        self.display_phone = display_phone
    
    def info_short(self):
        info_short_str = self.name + ', review count=' + str(self.review_count) 
        info_short_str += ', rating=' + str(self.rating) + ', price level=' + self.price_level
        return info_short_str

def get_locale_code():
    ''' Get locale code of supported country of this app.

    Parameters
    ----------
    None

    Returns
    -------
    locale_code: dict
        key is a country name in lowercase without space and 
        value is a yelp supported country code
    '''
    locale_url = 'https://www.yelp.com/developers/documentation/v3/supported_locales'
    CACHE_DICT = load_cache()
    locale_response = make_url_request_using_cache_html(locale_url, CACHE_DICT)

    locale_soup = BeautifulSoup(locale_response, 'html.parser')
    locale_list_parent = locale_soup.find('tbody').find_all('tr')

    locale_code = {}
    for locale in locale_list_parent:
        locale_content = locale.find_all('td')

        if locale_content[2].text == 'English':
            country = locale_content[1].text.lower().replace(' ', '')
            code = locale_content[0].text
            locale_code[country] = code
    
    # Insert data into database
    sql_statement = '''
    DROP TABLE IF EXISTS 'Locale'
    '''
    cur.execute(sql_statement)

    sql_statement = '''
    CREATE TABLE "Locale" (
    "Id"	INTEGER,
    "country"	TEXT,
    "locale_code"	TEXT,
    "alpha2"	TEXT,
    PRIMARY KEY("Id" AUTOINCREMENT)
    )
    '''
    cur.execute(sql_statement)
        
    for key,value in locale_code.items():
        alpha2 = value.split('_')[1]
        sql_statement = '''
        INSERT OR IGNORE INTO Locale 
        VALUES (NULL, ?, ?, ?)
        '''
        locale_code_insertion = [key, value, alpha2]
        cur.execute(sql_statement, locale_code_insertion)
        conn.commit()
    return locale_code
    
def get_categories_list():
    ''' Get a list of yelp categories of restaurants.

    Parameters
    ----------
    None

    Returns
    -------
    category_list: list
        a list of categories
    '''
    with open ('categories.json', 'r') as load_category_file:
        load_dict = json.load(load_category_file)
    
    category_list = []

    sql_statement = '''
    DROP TABLE IF EXISTS 'Categories'
    '''
    cur.execute(sql_statement)

    sql_statement = '''
    CREATE TABLE "Categories" (
	"Id"	INTEGER,
	"category"	TEXT,
	PRIMARY KEY("Id" AUTOINCREMENT)
    );
    '''
    cur.execute(sql_statement)

    for item in load_dict:
        try:
            if item['parents'][0] == "restaurants":
                category_list.append(item['alias'])
                sql_statement = '''
                INSERT OR IGNORE INTO Categories
                VALUES (NULL, ?)
                '''
                category_insertion = [item['alias']]
                cur.execute(sql_statement, category_insertion)
                conn.commit()
        except:
            pass
    
    return category_list

def process_input_country(country):
    ''' Process the user input of a valid country name

    Parameters
    ----------
    country: string
        user's input of a country name
    
    Returns
    -------
    None
    '''
    locale_code_dict = get_locale_code()
    country_input = country.lower().replace(' ', '')

    if country == 'list':
        for key in locale_code_dict.keys():
            print('{str:18}'.format(str = key))
        print()

    elif country_input in locale_code_dict.keys():
        country_locale_code = locale_code_dict[country_input]
        url_pieces = 'locale=' + country_locale_code
        sentence_1 = 'You are now searching in ' + country + '. '
        sentence_2 = 'Please Enter a city (type \'exit\' to quit.) : '
        input_query = sentence_1 + sentence_2
        city = input(input_query)
        
        if city == 'exit':
            quit()
        else:
            city_input = city.lower().replace(' ','')
        
        url_pieces = url_pieces + '&location=' + city_input
        process_category_input(city, url_pieces)

    else:
        print('Sorry, please input a valid country name.')
    
def process_category_input(city, url_pieces):
    ''' Process the user input of a valid category with ability of fuzzy matching

    Parameters
    ----------
    city: string
        user input of a city
    
    url_pieces: string
        the component of a url which is to be requested upon
    
    Returns
    -------
    None
    '''
    sentence_1 = 'You are now searching in ' + city
    sentence_2 = '. Please choose a restaurant category （type \'list\' to see all valid categories. '
    sentence_3 = 'type \'exit\' to quit. You can just enter first five letters for fuzzy matches.）: '
    input_query = sentence_1 + sentence_2 + sentence_3
    flag = True
    category = ''
    category_list = get_categories_list()
    
    # get category parameter
    while flag:
        category_input = input(input_query).strip().lower()
        
        if category_input == 'list':
            for x in range(len(category_list)):
                if x%7 != 0:
                    if len(category_list[x]) <= 16:
                        print("{str:20}".format(str = category_list[x]), end = '')
                    else:
                        print(category_list[x][0:16] + '... ', end = '')
                else:
                    print()
                    if len(category_list[x]) <= 16:
                        print("{str:20}".format(str = category_list[x]), end = '')
                    else:
                        print(category_list[x][0:16] + '... ', end = '')
            print()
            continue
        
        if category_input == 'exit':
            print('Bye. Have a nice day!')
            quit()
        
        # Fuzzy Searching
        if category_input in category_list:
            category = category_input
            flag = False
        else:
            for category_i in category_list:
                if (category_input in category_i) and len(category_input) >= 5:
                    flag_2 = True
                    while flag_2:
                        response_searching = input('Are you searching for ' + category_i + '? (Y/N) ').lower().strip()
                        if response_searching == 'y':
                            category = category_i
                            flag = False
                            flag_2 = False
                        elif response_searching == 'n':
                            flag_2 = False
                        else:
                            print("Invalid input.")
                    if flag == False:
                        break
                    else:
                        continue
            if category == '':
                flag = True
    
    url_category = BASE_URL_SEARCH + url_pieces + '&categories=' + category + '&limit=50'
    process_recommend_input(url_category)

def process_recommend_input(url_category):
    ''' Process user input of care level.

    Parameters
    ----------
    url_category: string
        the component of a url which is to be requested upon
    
    Returns
    -------
    None
    '''
    business_instance_list = get_business_instance_list(url_category)
    
    if len(business_instance_list) == 0:
        print('No such category of restaurants here.')
    elif len(business_instance_list) <= 2:
        print('Only ' + str(len(business_instance_list)) + ' restaurants of this category found:\n')
        for business_instance in business_instance_list:
            print('[' + str(business_instance_list.index(business_instance)) + '] ', end='')
            prompt_print(business_instance)
    else:
        # recommend restaurants according to user's input
        print(str(len(business_instance_list)) + ' restaurants match')
        print()

        while True:
            care_most_res = input('What do you care MOST when making your choice? \na. Price  b. Rating  c. Review count\n' + 
                '(Due to the limitation of the data source, you may type \'c\' here for best visualization): ').strip().lower()
            print()
            if care_most_res == 'a':
                care_most = 'price_level'
                break
            elif care_most_res == 'b':
                care_most = 'rating'
                break
            elif care_most_res == 'c':
                care_most = 'review_count'
                break
            elif care_most_res == 'exit':
                quit()
            else:
                print('Invalid Input.')
        
        while True:
            care_least_res = input('What do you care LEAST when making your choice? \na. Price  b. Rating  c. Review count\n: ').strip().lower()
            print()
            if care_least_res == care_most_res:
                print('Your care least option can not be the same with care most option.')
                continue
            if care_least_res == 'a':
                care_least = 'price_level'
                break
            elif care_least_res == 'b':
                care_least = 'rating'
                break
            elif care_least_res == 'c':
                care_least = 'review_count'
                break
            elif care_least_res == 'exit':
                quit()
            else:
                print('Invalid Input.')
        
        # determine the care list
        care_list_origin = ['price_level', 'rating', 'review_count']
        care_list = []
        care_list.append(care_most)
        care_list.append(care_least)
        for care in care_list_origin:
            if care not in care_list:
                care_list.append(care)
        care_tmp = care_list[1]
        care_list[1] = care_list[2]
        care_list[2] = care_tmp

        process_recommend_care_list(care_list)

def process_recommend_care_list(care_list):
    ''' Process user input of care level and calculate the recommendation score.

    Parameters
    ----------
    care_list: list
        a list of user's care level according to the items' rank
    
    Returns
    -------
    None
    '''
    care_weight_dict = {}
    care_weight_dict[care_list[0]] = 0.6
    care_weight_dict[care_list[1]] = 0.3
    care_weight_dict[care_list[2]] = 0.1

    sql_statement = '''
        SELECT Business.review_count, Business.rating, Business.price_level
        FROM Business
        ORDER BY Business.Id ASC
    '''
    response_raw_data = cur.execute(sql_statement).fetchall()

    review_count_list = []
    rating_list = []
    price_level_list = []
    for response in response_raw_data:
        review_count_list.append(response[0])
        rating_list.append(response[1])
        if response[2] != 6:
            price_level_list.append(response[2])
    review_count_max = max(review_count_list)
    rating_max = max(rating_list)
    price_level_max = max(price_level_list)

    for response in response_raw_data:
        recommendation_score = \
            (response[0] / review_count_max) * care_weight_dict['review_count'] + \
            (response[1] / rating_max) * care_weight_dict['rating'] + \
            (1 - (response[2] /  price_level_max)) * care_weight_dict['price_level']
        business_id = response_raw_data.index(response) + 1
        sql_statement_recommendation_score = '''
            UPDATE Business
            SET recommendation_score = ?
            WHERE Business.Id = ?
        '''
        sql_statement_recommendation_score_update = [recommendation_score, business_id]
        cur.execute(sql_statement_recommendation_score, sql_statement_recommendation_score_update)
        conn.commit()
    
    visualize_recommendation(care_weight_dict)

def visualize_recommendation(care_weight_dict):
    ''' Process user input of visualization command.

    Parameters
    ----------
    care_weight_dict: dict
        a dictionary of user's care level and weight

    Returns
    -------
    None
    '''
    vis_response = ''
    while vis_response != 'back':
        vis_response = input('Input visualization command: (\'back\', \'help\', \'exit\' or commands): ')

        if vis_response == 'back':
            pass
        elif vis_response == 'exit':
            print('Bye. Have a nice day!')
            quit()
        elif vis_response == 'help':
            with open('FinalProjVisualizationHelp.txt') as f:
                print(f.read())
        else:
            vis_res_list = vis_response.split()
            if vis_res_list[0] == 'bar':
                process_bar_chart(vis_res_list)
            elif vis_res_list[0] == 'scatter':
                process_scatter_chart(vis_res_list, care_weight_dict)
            elif vis_res_list[0] == 'pie':
                process_pie_chart(vis_res_list)
            elif vis_res_list[0] == 'bubble':
                process_bubble_chart(vis_res_list, care_weight_dict)
            else:
                print('Invalid Input.')        

def process_bar_chart(vis_res_list):
    ''' Visualizing data in bar chart and print recommendation info.
    
    Parameters
    ----------
    vis_res_list: list
        a list of words in user's input command
    
    Returns
    -------
    None
    '''
    while True:
        list_loc = 0
        if len(vis_res_list) != 2 and len(vis_res_list) != 1:
            print('Invalid input')
            break
        elif len(vis_res_list) == 2:
            if vis_res_list[1] == 'review':
                sql_selection = 'review_count'
                list_loc = 1
            elif vis_res_list[1] == 'rating':
                sql_selection = 'rating'
                list_loc = 2
            elif vis_res_list[1] == 'price':
                sql_selection = 'price_level'
                list_loc = 3
            else:
                print('Invalid input')
                break
        else:
            sql_selection = 'recommendation_score'
            list_loc = 4
        
        sql_statement_bar = '''
            SELECT Business.name, Business.review_count, Business.rating, 
            Business.price_level, Business.recommendation_score, 
            Business.location_display_address, Business.display_phone
            FROM Business
            WHERE NOT Business.price_level=6
            ORDER BY {} DESC
        '''.format(sql_selection)

        result_list = cur.execute(sql_statement_bar).fetchall()

        # Bar plot
        result_x_axis = []
        result_y_axis = []
        result_info = []
        for result in result_list:
            result_x_axis.append(result[0])
            result_y_axis.append(result[list_loc])
            if result_list.index(result) <= 6:
                info_str = '[' + str(result_list.index(result) + 1) + '] ' + result[0] + ', recommendation score is {rs:0.3f}'.format(rs=result[4])
                info_str += ', with review_count=' + str(result[1]) + ', price_level=' + str(result[3])
                info_str += ', rating=' + str(result[2]) +'. Address: ' + result[5] + '. Phone: ' + result[6] 
                result_info.append(info_str)
        bar_data = go.Bar(x=result_x_axis, y=result_y_axis)
        try:
            basic_layout = go.Layout(title = 'Top 7 matches sorting by ' +  vis_res_list[1].upper())
        except:
            basic_layout = go.Layout(title = 'Top 7 matches sorting by RECOMMENDATION SCORE')
        fig = go.Figure(data = bar_data, layout = basic_layout)
        fig.show()

        print('*' * len(result_info[-1]))
        for info in result_info:
            print(info)
        print('*' * len(result_info[-1]))
        break

def process_scatter_chart(vis_res_list, care_weight_dict):
    ''' Visualizing data in scatter chart and print recommendation info.
    
    Parameters
    ----------
    vis_res_list: list
        a list of words in user's input command
    
    Returns
    -------
    None
    '''
    while True:
        scatter_flag_2d = False
        scatter_flag_3d = False

        if len(vis_res_list) == 2:
            if vis_res_list[1] == '3d':
                scatter_flag_3d = True
            elif vis_res_list[1] == '2d':
                scatter_flag_2d = True
            else:
                print('Invalid input')
                break
        elif len(vis_res_list) == 1:
            scatter_flag_3d = True
        else:
            print('Invalid input')
            break

        if scatter_flag_2d:
            for key,value in care_weight_dict.items():
                if value == 0.6:
                    x_axis_lable = key # review_count, price_level, rating
                if value == 0.3:
                    y_axis_lable = key
            
            sql_statement_scatter = '''
                SELECT Business.name, Business.{}, Business.{}, 
                Business.recommendation_score, 
                Business.location_display_address, 
                Business.display_phone
                FROM Business
                ORDER BY Business.recommendation_score DESC
            '''.format(x_axis_lable, y_axis_lable)
            result_list = cur.execute(sql_statement_scatter).fetchall()
            
            # 2d scatter plot
            result_x_axis = []
            result_y_axis = []
            hover_text = []
            result_info = []
            for result in result_list:
                result_x_axis.append(result[1])
                result_y_axis.append(result[2])
                hover_text.append(result[0] + '<br>recom_score={rs:0.3f}'.format(rs=result[3]))
                if result_list.index(result) <= 6:
                    info_str = '[' + str(result_list.index(result) + 1) + '] ' + result[0] + ', recommendation score is {rs:0.3f}'.format(rs=result[3])
                    info_str += ', with {}='.format(x_axis_lable) + str(result[1]) + ', {}='.format(y_axis_lable) + str(result[2])
                    info_str += '. Address: ' + result[4] + '. Phone: ' + result[5] 
                    result_info.append(info_str)
            scatter_data = go.Scatter(
                x=result_x_axis, 
                y=result_y_axis, 
                hovertext=hover_text, 
                mode='markers',
                marker={
                    'symbol': 'star',
                    'size': 20,
                    'color': 'magenta'
                })
            basic_layout = go.Layout(title = '<2D Scatter Plot> x:{}  y:{}'.format(x_axis_lable, y_axis_lable))
            fig = go.Figure(scatter_data, layout=basic_layout)
            fig.show()

            print('*' * len(result_info[-1]))
            for info in result_info:
                print(info)
            print('*' * len(result_info[-1]))            
            break

        if scatter_flag_3d:
            for key,value in care_weight_dict.items():
                if value == 0.6:
                    x_axis_lable = key
                if value == 0.3:
                    y_axis_lable = key
                if value == 0.1:
                    z_axis_lable = key
            sql_statement_scatter = '''
                SELECT Business.name, 
                Business.{}, Business.{}, Business.{}, 
                Business.recommendation_score, 
                Business.location_display_address, 
                Business.display_phone
                FROM Business
                ORDER BY Business.recommendation_score DESC
            '''.format(x_axis_lable, y_axis_lable, z_axis_lable)
            result_list = cur.execute(sql_statement_scatter).fetchall()

            # 3d scatter plot
            result_x_axis = []
            result_y_axis = []
            result_z_axis = []
            hover_text = []
            result_info = []
            for result in result_list:
                result_x_axis.append(result[1])
                result_y_axis.append(result[2])
                result_z_axis.append(result[3])
                hover_text.append('<br>' + result[0] + '<br>recom_score={rs:0.3f}'.format(rs=result[4]))
                if result_list.index(result) <= 6:
                    info_str = '[' + str(result_list.index(result) + 1) + '] ' + result[0] + ', recommendation score is {rs:0.3f}'.format(rs=result[4])
                    info_str += ', with {}='.format(x_axis_lable) + str(result[1]) + ', {}='.format(y_axis_lable) + str(result[2])
                    info_str += ', {}='.format(z_axis_lable) + str(result[3]) +'. Address: ' + result[5] + '. Phone: ' + result[6] 
                    result_info.append(info_str)
            scatter_data_3d = go.Scatter3d(
                x=result_x_axis, 
                y=result_y_axis, 
                z=result_z_axis,
                hovertext=hover_text,
                mode='markers',
                marker={
                    'symbol': 'circle',
                    'size': 8,
                    'color': 'magenta'
                })
            basic_layout = go.Layout(title = 
                '<3D Scatter Plot>  x:{}  y:{}  z:{}'.format(
                    x_axis_lable, y_axis_lable, z_axis_lable
                ))
            fig = go.Figure(scatter_data_3d, layout=basic_layout)
            fig.show()

            print('*' * len(result_info[-1]))
            for info in result_info:
                print(info)
            print('*' * len(result_info[-1]))            
            break

def process_pie_chart(vis_res_list):
    ''' Visualizing data in pie chart and print recommendation info.
    
    Parameters
    ----------
    vis_res_list: list
        a list of words in user's input command
    
    Returns
    -------
    None
    '''
    while True:
        sql_selection = ''
        if len(vis_res_list) != 2:
            print('Invalid input')
            break
        else:
            if vis_res_list[1] == 'review':
                sql_selection = 'review_count'
            elif vis_res_list[1] == 'rating':
                sql_selection = 'rating'
            elif vis_res_list[1] == 'price':
                sql_selection = 'price_level'
            else:
                print('Invalid input')
                break
        

        sql_statement_pie = '''
            SELECT Business.name, 
            Business.review_count, Business.rating, Business.price_level,
            Business.recommendation_score,
            Business.location_display_address,
            Business.display_phone
            From Business
            ORDER BY Business.recommendation_score DESC
        '''

        result_list = cur.execute(sql_statement_pie).fetchall()

        # Pie plot
        review_count_list_pie = []
        rating_list_pie = []
        price_level_pie = []
        result_info = []

        for result in result_list:
            review_count_list_pie.append(result[1])
            rating_list_pie.append(result[2])
            price_level_pie.append(result[3])
            if result_list.index(result) <= 6:
                info_str = '[' + str(result_list.index(result) + 1) + '] ' + result[0] + ', recommendation score is {rs:0.3f}'.format(rs=result[4])
                info_str += ', with review_count=' + str(result[1]) + ', price_level=' + str(result[3])
                info_str += ', rating=' + str(result[2]) +'. Address: ' + result[5] + '. Phone: ' + result[6] 
                result_info.append(info_str)

        if sql_selection == 'review_count':
            labels = ['>2500', '1500~2500', '800~1499', '500~799','<500']
            values = [0,0,0,0,0]
            for review in review_count_list_pie:
                try:
                    if review > 2500:
                        values[0] += 1
                    elif review >= 1500 and review <= 2500:
                        values[1] += 1
                    elif review >= 800 and review <= 1499:
                        values[2] += 1
                    elif review >= 500 and review <= 799:
                        values[3] += 1
                    elif review < 500:
                        values[4] += 1
                    else:
                        pass
                except:
                    pass
        elif sql_selection == 'rating':
            labels = ['5.0', '4.5', '4.0', '3.5', '<3.5']
            values = [0,0,0,0,0]
            for rating in rating_list_pie:
                try:
                    if rating == 5.0:
                        values[0] += 1
                    elif rating == 4.5:
                        values[1] += 1
                    elif rating == 4.0:
                        values[2] += 1
                    elif rating == 3.5:
                        values[3] += 1
                    elif rating < 3.5:
                        values[4] += 1
                    else:
                        pass
                except:
                    pass     
        else:
            labels = ['Extremely High 5', 'Very High 4', 'High 3', 'Medium 2', 'Low 1']
            values = [0,0,0,0,0]
            for price in price_level_pie:
                try:
                    if price == 5:
                        values[0] += 1
                    elif price == 4:
                        values[1] += 1
                    elif price == 3:
                        values[2] += 1
                    elif price == 2:
                        values[3] += 1
                    elif price == 1:
                        values[4] += 1
                    else:
                        pass
                except:
                    pass

        colors = ['gold', 'mediumturguoise', 'darkorange', 'lightgreen', 'magenta']
        fig = go.Figure(data=[go.Pie(
            labels = labels,
            values = values,
        )])
        fig.update_traces(
            hoverinfo = 'label+percent',
            textinfo = 'value',
            textfont_size = 20,
            marker = dict(colors = colors, line = dict(color = '#000000', width = 2))
        )
        fig.update_layout(title_text = 'Pie Plot for {}'.format(sql_selection.upper()), titlefont_size = 40)
        fig.show()

        print('*' * len(result_info[-1]))
        for info in result_info:
            print(info)
        print('*' * len(result_info[-1]))            
        break

def process_bubble_chart(vis_res_list, care_weight_dict):
    ''' Visualizing data in bubble chart and print recommendation info.
    
    Parameters
    ----------
    vis_res_list: list
        a list of words in user's input command
    
    Returns
    -------
    None
    '''
    while True:
        # command can only be 'bubble'
        if vis_res_list == ['bubble']:
            pass
        else:
            print('Invalid input')
            break

        for key,value in care_weight_dict.items():
            if value == 0.6:
                x_axis_lable = key
            if value == 0.3:
                y_axis_lable = key
        
        xval = []
        yval = []
        text = []
        size = []
        color = []
        result_info = []

        sql_statement_bubble = '''
            SELECT Business.name, 
            Business.{}, Business.{},
            Business.recommendation_score,
            Business.location_display_address,
            Business.display_phone
            From Business
            ORDER BY Business.recommendation_score DESC
        '''.format(x_axis_lable, y_axis_lable)
        result_list = cur.execute(sql_statement_bubble).fetchall()

        for result in result_list:
            xval.append(result[1])
            yval.append(result[2])
            text.append(result[0] + '<br>' + 'recom_score={rs:0.3f}'.format(rs=result[3]))
            size.append(int(250*result[3]*result[3]*result[3]))
            color.append('rgb({},{},{})'.format(
                random.randint(1,255), 
                random.randint(1,255), 
                random.randint(1,255)))
            if result_list.index(result) <= 6:
                info_str = '[' + str(result_list.index(result) + 1) + '] ' + result[0] + ', recommendation score is {rs:0.3f}'.format(rs=result[3])
                info_str += ', with {}='.format(x_axis_lable) + str(result[1]) + ', {}='.format(y_axis_lable) + str(result[2])
                info_str += '. Address: ' + result[4] + '. Phone: ' + result[5] 
                result_info.append(info_str)
        
        fig = go.Figure(data=go.Scatter(
            x=xval, y=yval,
            text=text,
            mode='markers',
            marker=dict(
                color=color,
                size=size
            )
        ))

        fig.show()

        print('*' * len(result_info[-1]))
        for info in result_info:
            print(info)
        print('*' * len(result_info[-1]))            
        break

def prompt_print(business_instance):
    ''' Print recommendation info if only one or two matches are found.

    Parameters
    ----------
    business_instance: object
        an instance of a business class
    
    Returns
    -------
    None
    '''
    try:
        info_str = business_instance.name + ', ' + 'with review_count='
        info_str += str(business_instance.review_count) + ', price_level='
        info_str += str(business_instance.price_level) + ', rating='
        info_str += str(business_instance.rating) + '. Address: '
        info_str += str(business_instance.location_display_address_list) + '. Phone: '
        info_str += str(business_instance.display_phone)
        print(info_str)
    except:
        pass
    
def get_business_instance_list(url_category):
    ''' Make a list of business instances from a specific url.

    Parameters
    ----------
    url_category: string
        the component of a url which is to be requested upon
    
    Returns
    -------
    business_instance_list: list
        a list of business instances
    '''
    CACHE_DICT = load_cache()
    business_response = make_url_request_using_cache(url_category, CACHE_DICT)
    
    business_list = business_response['businesses'] # a list of business dict
    business_instance_list = []

    if len(business_list) == 0:
        return []
    else:
        for business in business_list:
            business_id = business['id']
            business_alias = business['alias']
            business_name = business['name']
            business_url = business['url']
            business_review_count = business['review_count']
            business_category_list = []
            for item in business['categories']:
                business_category_list.append(item['title'])
            business_rating = business['rating']
            price_level_list = [1, 1, 2, 3, 4, 5, 6]
            try:
                business_price_level = price_level_list[len(business['price']) + 1]
            except:
                business_price_level = price_level_list[0]
            business_location_zip_code = business['location']['zip_code']
            business_location_city = business['location']['city']
            business_location_state = business['location']['state']
            business_location_country = business['location']['country']
            business_display_address_list = business['location']['display_address']
            business_display_phone = business['display_phone']

            business_instance = Business(business_id, business_alias, business_name, business_url,
                business_review_count, business_category_list, business_rating, business_price_level,
                business_location_zip_code, business_location_city, business_location_state, 
                business_location_country, business_display_address_list, business_display_phone)
            
            business_instance_list.append(business_instance)

        # Insert data into database
        sql_statement_drop = '''
            DROP TABLE IF EXISTS "Business"
        '''
        cur.execute(sql_statement_drop)
        
        sql_statement_creat = '''
            CREATE TABLE IF NOT EXISTS "Business" (
            "id"	INTEGER,
            "yelp_id"	TEXT NOT NULL,
            "alias"	TEXT,
            "name"	TEXT NOT NULL,
            "url"	TEXT,
            "review_count"	INTEGER,
            "category_1"	TEXT,
            "category_2"	TEXT,
            "category_3"	TEXT,
            "rating"	REAL,
            "price_level"	INTEGER,
            "location_zip_code"	TEXT,
            "location_city"	TEXT,
            "location_state"	TEXT,
            "location_country"	INTEGER,
            "location_display_address"	TEXT,
            "display_phone"	TEXT,
            "recommendation_score"	REAL,
            PRIMARY KEY("Id" AUTOINCREMENT)
        )
        '''
        cur.execute(sql_statement_creat)

        for instance in business_instance_list:

            v1 = instance.id
            try:
                v2 = instance.alias
            except:
                v2 = 'Null'
            try:
                v3 = instance.name
            except:
                v3 = 'Null'
            try:
                v4 = instance.url
            except:
                v4 = 'Null'
            try:
                v5 = instance.review_count
            except:
                v5 = 0
            try:
                v6 = instance.category_title_list[0]
            except:
                v6 = 'Null'
            try:
                v7 = instance.category_title_list[1]
            except:
                v7 = 'Null'
            try:
                v8 = instance.category_title_list[2]
            except:
                v8 = 'Null'
            try:
                v9 = instance.rating
            except:
                v9 = 0.0
            try:
                v10 = instance.price_level
            except:
                v10 = 6
            try:
                v11 = instance.location_zip_code
            except:
                v11 = 'Null'
            try:
                v12 = instance.location_city
            except:
                v12 = 'Null'
            try:
                v13 = instance.location_state
            except:
                v13 = 'Null'
            try:
                # v14 is a foreign key referred to Locale.country
                v14 = instance.location_country
                sql_statement_country = '''
                    SELECT Locale.aplha2 FROM Locale
                '''
                res = cur.execute(sql_statement_country).fetchall()
                for r in res:
                    if v14 in r:
                        v14 = res.index(r) + 1
            except:
                v14 = 12
            try:
                v15 = ''
                for address in instance.location_display_address_list:
                    v15 = v15 + address + ' '
                v15 = v15.strip()
            except:
                v15 = 'Null'
            try:
                v16 = instance.display_phone
            except:
                v16 = 'Null'
            v17 = 0.0
            
            sql_statement = '''
            INSERT OR IGNORE INTO Business
            VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''

            business_instance_value = [
                v1, v2, v3, v4,
                v5, v6, v7, v8,
                v9, v10, v11, v12,
                v13, v14, v15, v16, v17
                ]
            cur.execute(sql_statement, business_instance_value)
            conn.commit()

        return business_instance_list

def load_cache():
    '''Loading cache file if it exists or set up a new one if not.
    
    Parameters
    ----------
    None
    
    Returns
    -------
    dict
        a cache dictionary
    '''
    try:
        cache_file = open('cache_final_proj.json', 'r')
        cache_file_contents = cache_file.read()
        cache = json.loads(cache_file_contents)
        cache_file.close()
    except:
        cache = {}
    return cache

def save_cache(cache):
    '''Saving cache file.
    
    Parameters
    ----------
    cache: dictionary
        a dictionary to be written into the cache file
    
    Returns
    -------
    None
    '''
    cache_file = open('cache_final_proj.json', 'w')
    contents_to_write = json.dumps(cache)
    cache_file.write(contents_to_write)
    cache_file.close()

def make_url_request_using_cache(url, cache):
    '''Making a url request using cache.
    
    Parameters
    ----------
    url: string
        a url to be requested upon
    
    cache: dictionary
        a dictionary with visited urls as keys and responses as values 
    
    Returns
    -------
    string
        a url string made with cache
    '''
    # database_inserted_flag = True
    if (url in cache.keys()):
        print('-' * len("Using cache: " + url))
        print("Using cache: " + url)
        print('-' * len("Using cache: " + url))
        return cache[url] #, database_inserted_flag
    else:
        print('-' * len("Fetching: " + url))
        print("Fetching: " + url)
        print('-' * len("Fetching: " + url))
        time.sleep(1)
        response = requests.get(url, headers=headers)
        cache[url] = response.json()
        save_cache(cache)
        # database_inserted_flag = False # we need to insert data to db
        return cache[url] #, database_inserted_flag

def make_url_request_using_cache_html(url, cache):
    '''Making a url request using cache.
    
    Parameters
    ----------
    url: string
        a url to be requested upon
    
    cache: dictionary
        a dictionary with visited urls as keys and responses as values 
    
    Returns
    -------
    string
        a url string made with cache
    '''
    if (url in cache.keys()):
        print('-' * len("Using cache: " + url))
        print("Using cache: " + url)
        print('-' * len("Using cache: " + url))
        return cache[url]
    else:
        print('-' * len("Fetching: " + url))
        print("Fetching: " + url)
        print('-' * len("Fetching: " + url))
        time.sleep(1)
        response = requests.get(url)
        cache[url] = response.text
        save_cache(cache)
        return cache[url]

def load_help_text():
    ''' Load FinalProjHelp.txt
    
    Parameters
    ----------
    None

    Returns
    -------
    f.read(): string
        content of FinalProjectHelp.txt
    '''
    with open('FinalProjHelp.txt') as f:
        return f.read()

def interactive_prompt():
    ''' Start a interaction with user.
    
    Parameters
    ----------
    None

    Returns
    -------
    None
    '''
    help_text = load_help_text()
    response = ''
    print('Hello, welcome to my app. I will recommend the best matched restaurants according to your input info. Let\'s go!')
    while response != 'exit':
        sentence_1 = 'Please Enter a valid country name (type \'exit\' to quit, '
        sentence_2 = 'type \'help\' to view help text, '
        sentence_3 = 'type \'list\' to see all valid country names): '
        input_query = sentence_1 + sentence_2 + sentence_3
        response = input(input_query)

        if response == 'help':
            print(help_text)
            continue

        if response == 'exit':
            print('Bye. Have a nice day!')
            quit()

        if response == '':
            continue

        process_input_country(response)

if __name__ == "__main__":
    interactive_prompt()