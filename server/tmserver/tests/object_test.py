from ..models import User, Room, Object
from .tm_test_case import TildemushTestCase

class ObjectTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.player = User(username='vilmibm', password='foobarbazquux')
        self.player.hash_password()
        self.player.save()

    def test_can_create_object_without_script(self):
        # as a player i can create an object
        obj = self.player.create_object(
            name='mr coffee',
            description='a helpful little robot for making drip coffee'
        )
        self.assertIsNotNone(obj.created_at)
        self.assertIsNotNone(obj.id)
        self.assertEqual(obj.owner.username, self.player.username)
        self.assertIsNone(obj.script)
        self.assertEqual(obj.name, 'mr coffee')
        self.assertEqual(obj.description, 'a helpful little robot for making drip coffee')

    def test_can_create_object_with_script(self):
        # TODO
        pass

    def test_requires_name(self):
        with self.assertRaisesRegex(ValueError, 'objects need a name'):
            self.player.create_object(name=None)

        with self.assertRaisesRegex(ValueError, 'objects need a name'):
            self.player.create_object(name='')

    def test_can_print(self):
        obj = self.player.create_object(name='mr coffee')
        self.assertEqual(str(obj), 'Object<{}> created by {} and owned by {}'.format(
            obj.name, self.player, self.player))

class ObjectOwnershipTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.player = User(username='vilmibm', password='foobarbazquux')
        self.player.hash_password()
        self.player.save()

        self.other_player = User(username='selfsame', password='foobarbazquux')
        self.other_player.hash_password()
        self.other_player.save()

        self.chemex = Object.create(name='chemex', description='too much effort', creator=self.player)
        self.frenchpress = Object.create(name='french press', description='best friend', creator=self.other_player)

    def test_check_inventory(self):
        # as a player i want to see what objects i'm carrying

        self.assertEqual(list(self.player.inventory), [])

        aeropress = self.player.create_object(
            name='aeropress',
            description='a weird tube ostensibly for making coffee')

        self.assertEqual(list(self.player.inventory), [aeropress])

        mr_coffee = self.player.create_object(
            name='mr. coffee',
            description='good friend')

        self.assertEqual(set(self.player.inventory), {aeropress, mr_coffee})

    def test_drop_object(self):
        # TODO as a player i want to drop an object
        pass

    def test_pickup_unanchored_object(self):
        # as a player i want to pick up an object
        self.player.pickup(self.chemex)
        self.assertEqual(list(self.player.inventory), [self.chemex])

    def test_pickup_anchored_object_not_created(self):
        # as a player i want to see an error when i try to pick up an anchored object
        #self.frenchpress.anchored = True
        #self.frenchpress.save()
        #with self.assertRaisesRegex(
        #        ValueError,
        #        'cannot pick up anchored object you did not create'):
        #    self.player.pickup(self.frenchpress)
        pass

    def test_pickup_anchored_object_created(self):
        # as a player i want to pick up an anchored object i created
        #self.chemex.anchored = True
        #self.chemex.save()
        #self.player.pickup(self.chemex)
        #self.assertEqual(list(self.player.inventory), [self.chemex])
        pass

    def test_cannot_re_pickup_object(self):
        # as a player i want to see an error if i try to pick up something i already carry
        self.player.pickup(self.chemex)
        with self.assertRaisesRegex(
                ValueError,
                'you already posess chemex'):
            self.player.pickup(self.chemex)


    def test_cannot_share_possession(self):
        # TODO as a player i want to see an error if i try to pick up something someone else is carrying
        self.other_player.pickup(self.chemex)
        with self.assertRaisesRegex(
                ValueError,
                'cannot get something already owned'):
            self.player.pickup(self.chemex)

    # TODO as a player i want to see what objects are in a room
    # TODO as a player i want to drop an object and anchor it to a room
    # TODO as a player i want to see an error when i try to pick up an anchored object i don't own
