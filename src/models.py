from typing import NamedTuple


class User(NamedTuple):
    Id: int
    UserName: str
    FirstName: str
    LastName: str
    FullName: str
    Description: str
    Email: str
    Img: str
    IsTeacher: bool

class Lesson(NamedTuple):
    Title: str
    Description: str

class Module(NamedTuple):
    Title: str
    Description: str
    Lessons: list[Lesson]

class Course(NamedTuple):
    Id: int
    Url: str
    ShortName: str
    CategoryId: int
    FullName: str
    Description: str
    Format: str
    TimeCreated: int
    TimeUpdated: int
    StartTime: int
    EndTime: int
    Language: str
    Program: list[Module] | None
    Users: list[User]


class ExistsUser(NamedTuple):
    Id: int
    Email: str
