from db import Database
from moodle import Moodle
import config


def main():
    cfg = config.load_config("../config.yaml")
    company = Moodle(cfg.MoodleToken, company_url=cfg.MoodleUrl)
    database = Database(user=cfg.DB.User, password=cfg.DB.Password, host=cfg.DB.Host, port=cfg.DB.Port, name=cfg.DB.Name)
    courses = company.get_all_courses()
    if not courses:
        exit("Нет курсов")

    for course in courses:
        print(course.FullName)
        database.add_course(course)

    database.close()


if __name__ == "__main__":
    main()
