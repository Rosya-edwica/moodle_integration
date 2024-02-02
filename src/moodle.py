import requests
from urllib.parse import urlencode
from models import *


class Moodle:
    def __init__(self, moodle_token: str, company_url: str):
        """
        Для того, чтобы успешно парсить курсы компании, нам нужно получить:
            moodle_token - токен компании, позволяющий получать доступ к ресурсам
            company_url - корневая ссылка компании для создания API-запросов (пример: https://ecdsdb.healthheuristics.org)
        """
        self.COMPANY_URL = company_url
        self.API_URL = f"{self.COMPANY_URL}/webservice/rest/server.php?"
        # Обязательный набор параметров для запроса
        self.API_PARAMS = {
            "wstoken": moodle_token,
            "moodlewsrestformat": "json"
        }

    def get_all_courses(self) -> list[Course] | None:
        """Основной метод, позволяющий получить полный список курсов вместе с участниками"""

        self.API_PARAMS["wsfunction"] = "core_course_get_courses" # Метод API, который выдаст нам список курсов
        resp = requests.get(self.API_URL + urlencode(self.API_PARAMS))
        if resp.status_code != 200:
            print("Проблемы с получением списка курсов:", resp.text)
            return None

        data = []
        for i in resp.json():
            if i["shortname"] == "STUDY": continue

            if i["format"] == "topics":
                program = self.get_course_program(i["id"])
            else:
                program = None
            data.append(Course(
                Id=i["id"],
                Url=f"{self.COMPANY_URL}/course/view.php?id={i['id']}",
                ShortName=i["shortname"],
                FullName=i["fullname"],
                CategoryId=i["categoryid"],
                Description=i["summary"],
                Format=i["format"],
                TimeCreated=i["timecreated"],
                TimeUpdated=i["timemodified"],
                Language=i["lang"],
                StartTime=i["startdate"],
                EndTime=i["enddate"],
                Program=program,
                Users=self.get_course_users(i["id"]),
            ))
        return data

    def get_course_program(self, course_id: int) -> list[Module] | None:
        """Парсим программу курса, которая бы соответсовала программам курсов Edwica"""

        self.API_PARAMS["wsfunction"] = "core_course_get_contents" # Метод API, выдающий содержание курса
        self.API_PARAMS["courseid"] = str(course_id)
        resp = requests.get(self.API_URL + urlencode(self.API_PARAMS))
        if resp.status_code != 200:
            print("Проблемы с получением программы курса:", resp.text)
            return None

        program = []
        for module in resp.json():
            lessons = []
            for lesson in module["modules"]:
                lessons.append( Lesson(
                    Title=lesson["name"],
                    Description="" # API не дает описание каждого урока
                ))
            program.append(Module(
                Title=module["name"],
                Description=module["summary"],
                Lessons=lessons
            ))
        return program

    def get_course_users(self, course_id: int) -> list[User] | None:
        self.API_PARAMS["wsfunction"] = "core_enrol_get_enrolled_users" # Метод API, выдающий участников курса
        self.API_PARAMS["courseid"] = str(course_id)
        resp = requests.get(self.API_URL + urlencode(self.API_PARAMS))
        if resp.status_code != 200:
            print("Проблемы с получением пользователей курса:", resp.text)
            return None

        users = []
        for i in resp.json():
             # Логика этого метода такова, что он выдает нам список абсолютно всех пользователей
             # Если у пользователя нет роли, значит он НЕ имеет отношения к этому курсу, поэтому мы его пропускаем
             # Если роль = student, то он ученик данного курса
             # Если роль = editedteacher, то это препод
            if not i["roles"] or i["firstname"] == "Администратор":
                continue

            is_teacher = False
            for role in i["roles"]:
                if "teacher" in role["shortname"]:
                    is_teacher = True
                    break

            user = User(
                Id=i["id"],
                UserName=i["username"],
                FirstName=i["firstname"],
                LastName=i["lastname"],
                FullName=i["fullname"],
                Description=i["description"],
                Email=i["email"],
                IsTeacher=is_teacher,
                Img=""
            )
            users.append(user)
        return users
