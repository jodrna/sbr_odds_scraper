import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from bs4 import BeautifulSoup as bs
from selenium import webdriver
import re
from unidecode import unidecode as decode


# functions to convert between us/decimal odds format
def pct_us(pctodds):
    return np.where(pctodds > 0.5, pctodds / (1 - pctodds) * (-100), (1 - pctodds) / pctodds * 100)


def us_pct(usodds):
    return 1 / np.where(usodds > 100, (usodds / 100) + 1, (100 / abs(usodds)) + 1)


# import lookup files needed for cleaning
player_names = pd.read_csv('~/Documents/mlb_analysis/lookups/players_sbr.csv')
team_names = pd.read_csv('~/Documents/mlb_analysis/lookups/teams_sbr.csv')


# use google chrome webdriver as opening of dialog boxes etc is required
driver = webdriver.Chrome("/Users/jordan/documents/mlb_analysis/chromedriver")
xpath = driver.find_element_by_xpath

# dates between which to scrape
start_date, end_date = '06/07/2017', '06/07/2017'

# create list of links to scrape
links = []

for x in range(0, 1 + ((datetime.strptime(end_date, '%d/%m/%Y'))-(datetime.strptime(start_date, '%d/%m/%Y'))).days):
    date = (datetime.strptime(start_date, '%d/%m/%Y')) + timedelta(days=x)
    link = "https://www.sportsbookreview.com/betting-odds/mlb-baseball/money-line/?date=" + (datetime.strftime(date, '%Y%m%d'))
    links.append(link)

# create empty table odds, iterate over created list of links and scrape data from each link, append to odds table, log will track game count per day
odds = []
log = []

for link in links:
    try:
        driver.get(link)
        driver.maximize_window()
        time.sleep(1)
        data = bs(driver.page_source, 'html.parser').find_all('div', {'class': re.compile('_3A-gC*')})
        log.append((len(data), link))
        xpath('//*[@id="bettingOddsGridContainer"]/div[3]/div[1]/div[2]/div/div').click()                   # turn off box scores
        g_id = 0

        for datum in data:
            g_id = g_id + 1
            game_time = bs(driver.page_source, 'html.parser').find('span', {'class': '_12kC7'}).string + datum.find_all('div', {'class': '_1t1eJ'})[0].next.string
            rot_num = datum.find_all('span', {'class': 'GBabE'})[0].string
            team_h = datum.find_all('a', {'class': '_3qi53'})[0].next.string
            team_a = datum.find_all('a', {'class': '_3qi53'})[1].next.string
            starter_h = datum.find_all('div', {'class': re.compile('_34bLJ _3XJBX*')})[0].string
            starter_a = datum.find_all('div', {'class': re.compile('_34bLJ _3XJBX*')})[1].string
            score_h = datum.find_all('div', {'class': re.compile('_2trL6')})[0].next.nextSibling.string
            score_a = datum.find_all('div', {'class': re.compile('_2trL6')})[0].next.string

            try:
                xpath('//*[@id="bettingOddsGridContainer"]/div[3]/div[' + str(g_id + 2) + ']/div[2]/div/div/div[2]/div/div/div/div/section[1]').click()  # line history
                time.sleep(1)
                moves = bs(driver.page_source, 'html.parser').find_all('div', {'class': '_13G-0'})

                for move in moves:
                    move_time = move.find_all('span', {'class': '_2YT4a'})[0].get_text()
                    ml_h = move.find_all('span', {'class': '_2YT4a'})[1].get_text()
                    ml_a = move.find_all('span', {'class': '_2YT4a'})[2].get_text()

                    odds.append((game_time, rot_num, team_h, starter_h, team_a, starter_a, score_h, score_a, move_time, ml_h, ml_a))

                xpath('// *[ @ id = "PageHandler"] / div[1] / div / span[2]').click()                            # close line history
            except:
                pass

        xpath('//*[@id="bettingOddsGridContainer"]/div[3]/div[1]/div[2]/div/div').click()                    # turn box scores back on

    except:
        try:
            xpath('//*[@id="bettingOddsGridContainer"]/div[3]/div[1]/div[2]/div/div').click()                 # turn box scores back on
        except:
            pass


# rename columns and format time columns
odds = pd.DataFrame(odds)
odds.columns = ['game_time', 'rot_num', 'team_h', 'starter_h', 'team_a', 'starter_a', 'score_h', 'score_a', 'move_time', 'h_ml', 'a_ml']
odds['game_time'] = pd.to_datetime(odds['game_time'], format='%a %b %d, %Y%I:%M %p')
odds['move_time'] = pd.to_datetime((odds['game_time'].dt.year.apply(str) + ' ' + odds['move_time']), format='%Y %m/%d %I:%M %p')
odds['season'] = odds['game_time'].dt.year.astype(str)
player_names['season'] = player_names['season'].astype(str)

# change from sbr format team name to my format, ie. nyy >> yankees
odds = pd.merge(odds, team_names, how='left', left_on='team_h', right_on='team_sbr')
odds = pd.merge(odds, team_names, how='left', left_on='team_a', right_on='team_sbr')
odds[['team_h', 'team_a']] = odds[['team_model_x', 'team_model_y']]
odds['park'] = np.where(odds['park_model_x'] == odds['park_model_y'], odds['park_model_x'], odds['park_model_x'] + '-IL')
odds = odds.dropna(subset=['team_h', 'team_a'])

# remove accents from player names, split handedness and name into separate columns, then change to first last instead of f.last format,
odds['starter_h'] = odds['starter_h'].apply(decode)
odds['starter_a'] = odds['starter_a'].apply(decode)
odds[['starter_h', 'hand_h']] = odds['starter_h'].str.replace(')', '').str.replace('(', '').str.rsplit(' ', n=1, expand=True)
odds[['starter_a', 'hand_a']] = odds['starter_a'].str.replace(')', '').str.replace('(', '').str.rsplit(' ', n=1, expand=True)
odds = pd.merge(odds, player_names, how='left', left_on=['starter_h', 'team_h', 'season'], right_on=['player_sbr', 'team_model', 'season'])
odds = pd.merge(odds, player_names, how='left', left_on=['starter_a', 'team_a', 'season'], right_on=['player_sbr', 'team_model', 'season'])
odds[['starter_h', 'starter_a']] = odds[['player_model_x', 'player_model_y']]
odds['h_ml'] = us_pct(odds['h_ml'])
odds['a_ml'] = us_pct(odds['a_ml'])

# remove redundant columns, duplicate rows, and reorder into final form
odds = odds.iloc[0:, np.r_[0, 1, 18, 2, 3, 19, 4, 5, 20, 6:12]]
odds = odds.drop_duplicates(keep='last')
odds = odds.sort_values(by=['game_time', 'rot_num', 'move_time'])

# export
odds.to_csv("~/documents/mlb_analysis/raw_data/odds.csv")
