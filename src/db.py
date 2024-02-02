import pymysql
from datetime import datetime
from time import time
import random
import string

from models import User, Course, ExistsUser


class Database:
    def __init__(self, user: str, password: str, host: str, port: int, name: str, edwica_token: str | None = None):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.name = name
        self.connection = self.connect()

    def connect(self):
        """Подключение к БД"""

        conn = pymysql.connect(
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            db=self.name
        )
        return conn

    def close(self):
        self.connection.close()


    def add_course(self, course: Course):
        """
        Здесь мы запускаем транзакцию, которая должна добавить данные в несколько таблиц сразу:
            - course - здесь будет основная информация о курсах; После вставки необходимо получить id курсов для связей с модулями и пользователями
            - subdomain_course - здесь будет проставлена связь между курсами и мудлом
            - course_module - здесь мы сохраним информацию о модулях курсах; После вставки необходимо получить id модулей для связей с уроками
            - course_lesson - здесь мы сохраним информацию о каждом уроке модуля
            - course_enrolments - здесь мы проставим связь между пользователем и курсом
        """

        # Старт транзакции
        try:
            self.connection.autocommit = False
            cursor = self.connection.cursor()

            # Добавляем пользователей и ждем их id из БД
            list_of_users_id = self.__add_users(course.Users, cursor)

            course_teacher_select_query = f"""SELECT user_id 
                FROM auth_assignment WHERE user_id IN ({','.join([str(i) for i in list_of_users_id])})
                AND item_name = 'teacher' LIMIT 1
             """
            cursor.execute(course_teacher_select_query)
            course_teacher_id = cursor.fetchone()[0]

            # Вставка курса
            course_insert_query = """INSERT INTO
                course(name, type, lang, start_at, description, created_at, updated_at, src, creator_id, is_public, alias, is_modules)
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            # Наполняем курс необходимыми данными в нужном формате
            is_moduled = True if len(course.Program) > 1 else False
            course_insert_values = (course.FullName, "course", course.Language, get_current_format_for_date(course.StartTime), 
                course.Description, datetime.fromtimestamp(course.TimeCreated), datetime.fromtimestamp(course.TimeUpdated), "moodle",
                course_teacher_id, True, transliterate(course.FullName), is_moduled)
            cursor.execute(course_insert_query, course_insert_values)

           # Вставляем один курс - поэтому можем смело брать его id
            inserted_course_id = cursor.lastrowid

            # Связываем курс с поддоменом
            cursor.execute(f"INSERT INTO subdomain_course(course_id, subdomain) VALUES({inserted_course_id}, 'moodle')")


            # Вставка модулей
            module_insert_query = """INSERT INTO
                course_module(name, course_id)
                VALUES(%s, %s)
            """
            if course.Program:
                module_insert_values = [(mod.Title, inserted_course_id) for mod in course.Program]
                cursor.executemany(module_insert_query, module_insert_values)

                # Так как мы не можем получить все module_id сразу, мы берем ПЕРВЫЙ и отчитываем от него количество вставленных элементов
                # Таким образом мы получим полный список module_id. Операция безопасна, так как module_id является AUTOINCREMENT
                first_id = cursor.lastrowid
                list_of_modules_id = list(range(first_id, len(module_insert_values)+first_id))

                # cursor.execute("SELECT id, name, course_id FROM course_module WHERE src = 'moodle' ORDER BY id DESC LIMIT 1")

                # Вставка уроков - для этого нам нужны module_id
                lesson_insert_query = """INSERT INTO
                    course_lesson(module_id, name, description, `order`)
                    VALUES(%s, %s, %s, %s)
                """
                # Наполняем список уроков, правильно сопоставляя их с модулями
                lesson_insert_values = []
                lessons_count = 0
                for idx, mod_id in enumerate(list_of_modules_id):
                    module = course.Program[idx] # Выбираем модуль по порядковому номеру из списка вставленных модулей
                    for lesson_idx, lesson in enumerate(module.Lessons, start=1):
                        # Добавляем в список уроков: айди модуля, название урока, описание урока и порядковый номер
                        lesson_insert_values.append((mod_id, lesson.Title, lesson.Description, lesson_idx))
                        lessons_count += 1
                cursor.executemany(lesson_insert_query, lesson_insert_values)


                # Вставка связей курса с пользователями
                users_to_course_insert_query = """INSERT INTO
                    user_enrolments(courseid, userid, created_at, current_lesson)
                    VALUES(%s, %s, %s, %s)
                """
                users_to_course_insert_values = [(inserted_course_id, user_id, datetime.now(), lessons_count) for user_id in list_of_users_id]
                cursor.executemany(users_to_course_insert_query, users_to_course_insert_values)


        except pymysql.Connect.Error as error:
            # Обработка ошибок транзакции
            print("Не удалось выполнить транзакцию:", error)
            self.connection.rollback()
        else:
            # Успешное выполнение транзакции
            self.connection.commit()
            ...
        finally:
            # Завершение
           cursor.close()


    def __add_users(self, users: list[User], cursor) -> list[int]:
        """
        Здесь мы продолжаем транзакцию:
            - user - здесь будет основная информация о пользователях (ученики, преподаватели); После вставки необходимо получить id пользователей с остальными таблицами
            - auth_assignment - здесь мы сохраним информацию о ролях пользователей;
            - auth - инфа для регистрации пользователя
        """
        # Проверяем сохраняли ли раньше мы этих пользователей
        exists_users = self.__find_exists_users(users, cursor)
        list_of_users_id = []
        for exists in exists_users:
            for user in users:
                if exists.Email == user.Email:
                    users.remove(user)
                    list_of_users_id.append(exists.Id)
                    break
            
        if not users:
            return list_of_users_id



        # Вставка списка пользователей
        user_insert_query = """INSERT INTO
            user(username, surname, name, auth_key, password_hash, email, status, created_at, updated_at, description, src)
            VALUES(%s, %s, %s, %s, 'test_password', %s, 10, %s, %s, %s, 'moodle')
        """

        timestamp = int(time()) # Время добавления пользователей
        user_insert_values = tuple(((user.UserName, user.LastName, user.FirstName, generate_auth_key(), user.Email, timestamp, timestamp, user.Description) for user in users))
        cursor.executemany(user_insert_query, user_insert_values)

        


        # Так как мы не можем получить все user_id сразу, мы берем последний и отчитываем от него количество вставленных элементов
        # Таким образом мы получим полный список user_id. Операция безопасна, так как user_id является AUTOINCREMENT
        last_id = cursor.lastrowid
        new_list_users_id = list(range(last_id - len(user_insert_values)+1, last_id+1))

        # Вставка данных в таблицу ролей
        auth_assignment_insert_query = """INSERT INTO
            auth_assignment(item_name, user_id, created_at)
            VALUES(%s, %s, %s)
        """
        # Вставка инфы откуда пришел пользователь
        auth_insert_query = """INSERT INTO
            auth(user_id, source, source_id)
            VALUES(%s, %s, %s)
        """

        auth_assignment_insert_values = []
        auth_insert_values = []

        # Здесь нам надо сопоставить полученные user_id с имеющимися пользователями
        # Сразу наполним список с данными о ролях и список с доп.инфой о пользователе
        for idx, item in enumerate(user_insert_values):
            for user in users:
                if item[0] == user.UserName:
                    role = "teacher" if user.IsTeacher else "student"
                    auth_assignment_insert_values.append((role, new_list_users_id[idx], timestamp))
                    auth_insert_values.append((new_list_users_id[idx], "moodle", user.Id))
                    break
        cursor.executemany(auth_assignment_insert_query, auth_assignment_insert_values)
        cursor.executemany(auth_insert_query, auth_insert_values)
        cursor.execute("""select user.id, user.name, user.surname, auth_assignment.item_name as 'role'
        from user
        left join user_enrolments on user_enrolments.userid = user.id
        left join auth_assignment on auth_assignment.user_id = user.id
        where user.src = 'moodle'
        order by user.id""")
        return list_of_users_id + new_list_users_id


    def __find_exists_users(self, users: list[User], cursor) -> list[ExistsUser]:
        """
        Перед тем как добавлять пользователей, нужно проверить сохраняли ли мы их ранее.
        Если да, то вернем список пользователей в виде (id записи в БД и почта для идентификации с теми пользователями, которые мы хотели сохранить)
        """
        cursor.execute(f"SELECT id, email FROM user WHERE src='moodle'")
        exists_users = [ExistsUser(*row) for row in cursor.fetchall()]
        return exists_users


def get_current_format_for_date(timestamp: int) -> str:
    """Переводим дату в стандарт: день.месяц.год"""
    if not timestamp:
        return ""
    date = datetime.fromtimestamp(timestamp)
    formatted_date = date.strftime("%d.%m.%Y")
    return formatted_date

def transliterate(name: str) -> str:
    """
    Функция для создания alias по названию курса. Пример:
    input: "привет мир"
    output: "privet-mir"
    """
    slovar = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e',
     'ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n',
     'о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
     'ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e',
     'ю':'yu','я':'ya', " ": "-"}
    for key in slovar:
        name = name.lower().replace(key, slovar[key])
    return name



def generate_auth_key() -> str:
    """
    Функция генерит случайный auth_key. 
    В идеале auth_key должен формироваться на стороне у Егора по такому же принципу, что и другие ключи с паролями
    """
    symbols = string.ascii_letters + "_-?&;,.1234567890"
    return "".join([random.choice(symbols) for _ in range(32)])