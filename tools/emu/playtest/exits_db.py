"""Exit/door tables transcribed from each floor's source, for the pathfinder.
Coordinates are (map_letter, x, y). Doors: (key_required, starts_open).

The 7th field of each EXITS entry is the exit's `heading` exactly as the
Exit struct in src/map.h stores it (UP/DOWN/LEFT/RIGHT/HERE) -- NOT the
stairs/hole/portal exit_type. That distinction matters: map.c's
MAP_STATE_EXIT_LOADED handler auto-walks the hero one more tile in
`heading` right after arrival, unless heading is HERE (every portal and
hole in the game uses HERE, so they're exempt; every stairs exit uses a
real direction, so they land one tile further than to_col/to_row). nav.py
applies that offset when resolving a destination; this table only needs
the raw heading.
"""

EXITS = {
1: [("A",4,8,"A",4,5,"UP"), ("A",4,5,"A",4,8,"DOWN"),
    ("A",12,12,"A",12,9,"UP"), ("A",12,9,"A",12,12,"DOWN"),
    ("A",16,13,"A",3,24,"DOWN"), ("A",3,24,"A",16,13,"DOWN"),
    ("A",6,29,"A",19,18,"DOWN"), ("A",19,18,"A",6,29,"DOWN"),
    ("A",9,23,"A",21,28,"UP"), ("A",21,28,"A",9,23,"DOWN"),
    ("A",12,3,None,10,13,"UP")],
2: [("A",10,8,"A",10,5,"UP"), ("A",10,5,"A",10,8,"DOWN"),
    ("A",3,10,"A",3,7,"UP"), ("A",3,7,"A",3,10,"DOWN"),
    ("A",17,10,"A",17,7,"UP"), ("A",17,7,"A",17,10,"DOWN"),
    ("A",18,16,"B",14,8,"DOWN"), ("B",14,8,"A",18,16,"DOWN"),
    ("A",9,19,"B",5,11,"DOWN"), ("B",5,11,"A",9,19,"DOWN"),
    ("A",11,19,"B",7,11,"DOWN"), ("B",7,11,"A",11,19,"DOWN"),
    ("B",6,2,"B",24,8,"UP"), ("B",24,8,"B",6,2,"DOWN"),
    ("A",10,1,None,26,17,"UP")],
3: [("A",26,14,"A",4,17,"UP"), ("A",4,17,"A",26,14,"DOWN"),
    ("A",24,14,"A",19,29,"DOWN"), ("A",19,29,"A",24,14,"DOWN"),
    ("A",28,14,"A",12,6,"DOWN"), ("A",12,6,"A",28,14,"DOWN"),
    ("A",14,29,"A",27,28,"UP"), ("A",27,28,"A",14,29,"DOWN"),
    ("A",17,6,"A",3,5,"UP"), ("A",3,5,"A",17,6,"DOWN"),
    ("A",4,12,None,24,30,"UP")],
4: [("A",28,27,"A",28,23,"UP"), ("A",28,23,"A",28,27,"DOWN"),
    ("A",19,27,"A",5,9,"DOWN"), ("A",5,9,"A",19,27,"DOWN"),
    ("A",1,8,"A",1,5,"UP"), ("A",1,5,"A",1,8,"DOWN"),
    ("A",20,27,"A",10,12,"UP"), ("A",10,12,"A",20,27,"DOWN"),
    ("A",21,27,"A",15,9,"DOWN"), ("A",15,9,"A",21,27,"DOWN"),
    ("A",19,8,"A",19,5,"UP"), ("A",19,5,"A",19,8,"DOWN"),
    ("A",28,19,None,12,30,"UP")],
5: [("A",3,18,"B",3,5,"UP"), ("B",3,5,"A",3,18,"DOWN"),
    ("A",26,6,"B",11,5,"UP"), ("B",11,5,"A",26,6,"DOWN"),
    ("A",2,9,"B",19,5,"UP"), ("B",19,5,"A",2,9,"DOWN"),
    ("B",3,1,None,8,7,"UP")],
6: [("A",8,1,"B",3,6,"UP"), ("B",3,6,"A",8,1,"DOWN"),
    ("A",2,18,"A",20,9,"UP"), ("A",20,9,"A",2,18,"DOWN"),
    ("A",12,19,"A",30,10,"UP"), ("A",30,10,"A",12,19,"DOWN"),
    ("A",4,20,"A",5,4,"HERE"), ("A",7,18,"A",8,2,"HERE"),
    ("A",10,20,"A",11,4,"HERE"), ("A",5,23,"A",6,7,"HERE"),
    ("A",21,21,"A",5,16,"HERE"), ("A",22,21,"A",7,3,"HERE"),
    ("A",21,22,"A",6,4,"HERE"), ("A",23,25,"A",7,20,"HERE"),
    ("A",24,24,"A",10,4,"HERE"), ("A",22,25,"A",8,5,"HERE"),
    ("B",3,2,None,8,30,"UP")],
7: [("A",8,26,"A",27,9,"UP"), ("A",27,9,"A",8,26,"DOWN"),
    ("A",7,26,"A",2,19,"UP"), ("A",2,19,"A",7,26,"DOWN"),
    ("A",9,26,"A",10,19,"UP"), ("A",10,19,"A",9,26,"DOWN"),
    ("A",1,28,"A",7,11,"HERE"), ("A",9,6,"A",7,29,"HERE"),
    ("A",15,28,"A",13,11,"HERE"), ("A",11,6,"A",9,29,"HERE"),
    ("A",24,7,"A",31,29,"LEFT"), ("A",31,29,"A",24,7,"RIGHT"),
    ("A",27,5,None,8,29,"UP")],
8: [("A",8,9,"A",8,6,"UP"), ("A",8,6,"A",8,9,"DOWN")],
}

DOORS = {
1: [("A",4,8,True,False), ("A",12,12,False,False), ("A",12,3,False,False), ("A",9,23,False,False)],
2: [("A",10,8,False,False), ("A",3,10,True,False), ("A",17,10,True,False),
    ("A",9,19,False,True), ("B",5,11,False,True), ("A",11,19,False,False), ("B",7,11,False,False),
    ("B",6,2,False,False), ("A",10,1,False,False)],
3: [("A",17,6,False,False), ("A",26,14,False,False), ("A",4,12,False,False)],
4: [("A",28,27,False,False), ("A",28,19,False,False), ("A",1,8,False,False), ("A",19,8,False,False)],
5: [("B",3,1,False,False), ("A",2,9,False,False), ("A",3,18,False,False)],
6: [("A",8,1,False,False), ("B",3,2,False,False), ("A",2,18,False,False), ("A",12,19,False,False)],
7: [("A",27,5,False,False), ("A",8,26,False,False), ("A",7,26,False,False), ("A",9,26,False,False),
    ("A",7,9,True,False), ("A",2,4,False,False), ("A",13,9,True,False), ("A",18,4,False,False)],
8: [("A",8,9,False,False), ("A",8,1,False,False)],
}
