# Anime & Manga Stack Exchange Data Analysis

## Project Overview

This project performs an in-depth analysis of the Anime & Manga Stack Exchange data dump. The goal is to uncover insights into community trends, popular topics, user engagement, and overall community health. The analysis is conducted using Python with libraries such as Pandas, Matplotlib, and Seaborn, all within a Jupyter Notebook.

## Key Findings

*   **Most Discussed Series:** Identification of the most frequently discussed anime and manga series.
*   **User Demographics:** Analysis of the geographic distribution of the community's user base.
*   **Community Activity:** Temporal analysis of post and comment activity to identify peak hours, days, and months.
*   **Content Trends:** Analysis of tag usage to understand which genres and topics are most popular.
*   **User Engagement:** Examination of reputation distribution and voting patterns to gauge user involvement.

## Project Structure

```
anime-stack-analysis/
├── .gitignore
├── data/
│   ├── raw/
│   │   ├── Posts.xml
│   │   └── ... (other .xml files)
│   └── processed/
│       ├── Posts.csv
│       └── ... (other .csv files)
├── images/
│   ├── most_discussed_anime.png
│   └── ... (other saved plots)
├── notebooks/
│   └── Anime StackViz.ipynb
├── README.md
└── requirements.txt
```

## Setup and Installation

To run this analysis yourself, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/M1hawk005/Anime-StackViz.git 

    cd Anime-StackViz
    ```

2.  **Create and activate a virtual environment.** 
    
    - If you are using `pyenv-venv`:
    ```bash
    pyenv virtualenv 3.13.5 anime-stack-venv

    #activate env
    pyenv-venv activate anime-stackviz-venv
    ```
    - If you are using `venv`
    ```bash
    python -m venv  .venv
    
    #activate env
    # On Windows
    .\.venv\Scripts\activate

    # On MacOS/Linux
    source .venv/bin/activate

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Launch Jupyter Notebook:**
    ```bash
    jupyter notebook
    ```
    Then, navigate to `notebooks/Anime StackViz.ipynb` and run the cells.

## Data Source

The data used in this analysis is from the official Stack Exchange Data Dump for the [Anime & Manga](https://anime.stackexchange.com/) site, available on the [Internet Archive](https://archive.org/details/stackexchange).

## Technologies Used

*   Python 3.13
*   pyenv/venv
*   Pandas & Numpy
*   Matplotlib & Seaborn
*   pyenv-win and pyenv-venv
*   Jupyter Notebook