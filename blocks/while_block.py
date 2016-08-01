'''
A module that implements WhileBlock and PWhileBlock, subclasses of ListBlock.
WhileBlocks are used where an array is needed which does not have a size
stored anywhere and must be parsed until some function says to stop.
'''
from .list_block import *


class WhileBlock(ListBlock):
    '''
    A Block class meant to be used with Fields that have an
    open ended size which must be deduced while parsing it.

    WhileBlocks function identically to ListBlocks, except that
    they have been optimized to only work with array Fields and
    all code regarding setting their size has been removed.
    This is because WhileArrays are designed to only be used with
    Fields that are open-ended and dont store their size anywhere.

    For example, WhileBlocks are used with WhileArrays, which continue
    to build array entries until a "case" function returns False.
    '''
    __slots__ = ('desc', 'parent')

    def __setitem__(self, index, new_value):
        '''
        Places 'new_value' into this Block at 'index'.
        index may be the string name of an attribute.

        If 'index' is a string, calls:
            self.__setattr__(index, new_value)
        '''
        if isinstance(index, int):
            # handle accessing negative indexes
            if index < 0:
                index += len(self)
            list.__setitem__(self, index, new_value)

            # if the object being placed in the Block has
            # a 'parent' attribute, set this block to it
            if hasattr(new_value, 'parent'):
                object.__setattr__(new_value, 'parent', self)

        elif isinstance(index, slice):
            # if this is an array, dont worry about the descriptor since
            # its list indexes aren't attributes, but instanced objects
            list.__setitem__(self, index, new_value)
        else:
            self.__setattr__(index, new_value)

    def __delitem__(self, index):
        '''
        Deletes an attribute from this Block located in 'index'.
        index may be the string name of an attribute.

        If 'index' is a string, calls:
            self.__delattr__(index)
        '''
        if isinstance(index, str):
            self.__delattr__(index)
            return
        elif isinstance(index, int) and index < 0:
            index += len(self)
        list.__delitem__(self, index)

    def append(self, new_attr=None, new_desc=None):
        '''
        Appends new_attr to this WhileBlock.

        If new_attr is None or not provided, this method will create
        an empty index on the end of the array and run the reader
        function of new_desc['TYPE'] to create a new default
        object of the proper python type to place in it.

        If new_desc is not provided, uses self.desc['SUB_STRUCT'] as it.
        '''
        # create a new, empty index
        list.append(self, None)

        # if this block is an array and "new_attr" is None
        # then it means to append a new block to the array
        if new_attr is None:
            if new_desc is None:
                new_desc = object.__getattribute__(self, 'desc')['SUB_STRUCT']
            new_desc['TYPE'].reader(new_desc, self, None, len(self) - 1)
            return

        try:
            list.__setitem__(self, -1, new_attr)
        except Exception:
            list.__delitem__(self, -1)
            raise
        try:
            object.__setattr__(new_attr, 'parent', self)
        except Exception:
            pass

    def extend(self, new_attrs):
        '''
        Extends this Block with 'new_attrs'.

        If new_attrs is a ListBlock, calls the below code:
            desc = new_attrs.desc[SUB_STRUCT]
            for i in range(len(new_attrs)):
                self.append(new_attrs[i], desc)

        If new_attrs is an int, appends 'new_attrs' count of new Block
        instances defined by the descriptor in:  self.desc[SUB_STRUCT].
        '''
        if isinstance(new_attrs, ListBlock):
            assert SUB_STRUCT in new_attrs.desc, (
                'Can only extend a WhileArray with another array type Block.')
            for attr in new_attrs:
                self.append(attr)

        elif isinstance(new_attrs, int):
            # if this block is an array and "new_attr" is an int it means
            # that we are supposed to append this many of the SUB_STRUCT
            for i in range(new_attrs):
                self.append()
        else:
            raise TypeError("Argument type for 'extend' must be an " +
                            "instance of ListBlock or int, not %s" %
                            type(new_attrs))

    def insert(self, index, new_attr=None, new_desc=None):
        '''
        Inserts 'new_attr' into this Block at 'index'.
        index may be the string name of an attribute.

        If new_attr is None, inserts a new Block defined by new_desc.
        If new_desc is None, uses self.desc[SUB_STRUCT] as new_desc.
        '''
        # create a new, empty index
        list.insert(self, index, None)

        if new_desc is None:
            new_desc = object.__getattribute__(self, 'desc')['SUB_STRUCT']
        new_field = new_desc['TYPE']

        try:
            # if the Field is a Block then we can
            # create one and just append it to the array
            if new_attr is None and new_field.is_block:
                new_field.reader(new_desc, self, None, index)
                # finished, so return
                return
        except Exception:
            list.__delitem__(self, index)
            raise
        try:
            list.__setitem__(self, index, new_attr)
        except Exception:
            list.__delitem__(self, index)
            raise
        try:
            object.__setattr__(new_attr, 'parent', self)
        except Exception:
            pass

    def pop(self, index=-1):
        '''
        Pops 'index' out of this Block.
        index may be the string name of an attribute.

        Returns a tuple containing it and its descriptor.
        '''
        desc = object.__getattribute__(self, "desc")

        if isinstance(index, int):
            if index < 0:
                return (list.pop(self, index + len(self)), desc['SUB_STRUCT'])
            return (list.pop(self, index), desc['SUB_STRUCT'])
        elif index in desc.get('NAME_MAP', ()):
            return (list.pop(self, desc['NAME_MAP'][index]),
                    self.get_desc('SUB_STRUCT'))

        raise AttributeError("'%s' of type %s has no attribute '%s'" %
                             (desc.get(NAME, UNNAMED), type(self), index))

    def set_size(self, new_value=None, attr_index=None, **context):
        '''
        Sets the size of the 'attr_index' element in this Block to
        'new_value' using the SIZE entry in self.desc[attr_index].
        If the attribute itself has a descriptor, uses its
        descriptor instead of the one in self.desc[attr_index]

        If 'new_value' isnt supplied, calculates it using the
        sizecalc method of the 'TYPE' entry in the descriptor.

        If the SIZE entry is a string, the size will be set using
        self.set_neighbor and providing the SIZE entry as the pathstring.

        If the SIZE entry is a function, the size will be set by doing:
            size_setter(attr_index=attr_index, new_value=new_value,
                        parent=self, block=block, **context)
        where size_setter is the function under the descriptors SIZE key,
        new_value is the calculated or provided value to set the size to,
        context is a dictionary of the remaining supplied keyword arguments,
        block is the attribute whose size is being set,
        and attr_index is the provided attr_index argument.

        If attr_index is an int, sets the size of self[attr_index].
        If attr_index is a str, sets the size of self.__getattr__(attr_index).
        If attr_index is None, this method will do nothing. This is because
        WhileBlocks are designed to express data which doesnt store a size.

        Raises DescEditError if the descriptor 'SIZE' entry
        is an int and the value the size is being set to is
        greater than what is currently in the descriptor.
        Raises DescKeyError if 'SIZE' doesnt exist in the descriptor.
        Raises TypeError if the 'SIZE' entry isnt an int, string, or function.
        '''
        self_desc = object.__getattribute__(self, 'desc')

        if isinstance(attr_index, str):
            attr_index = self_desc['NAME_MAP'][attr_index]
        elif not isinstance(attr_index, int):
            # cant set size of WhileArrays
            return

        block = self[attr_index]
        # try to get the size directly from the block
        try:
            desc = block.desc
            size = self_desc['SIZE']
            error_num = 0
        except Exception:
            # if that fails, try to get it from the desc of the parent
            desc = self_desc[attr_index]

            try:
                size = desc['SIZE']
                error_num = 0
            except Exception:
                # its parent cant tell us the size, raise this error
                error_num = 1
                if 'TYPE' in desc and not desc['TYPE'].is_var_size:
                    # the size is not variable so it cant be set
                    # without changing the type. raise this error
                    error_num = 2

        if error_num:
            field = desc['TYPE']
            if error_num == 1:
                raise DescKeyError("Could not locate size for " +
                                   "attribute '%s' in block '%s'." %
                                   (desc.get('NAME', UNNAMED),
                                    self_desc.get('NAME', UNNAMED)))
            raise DescKeyError(("Can not set size for attribute " +
                                "'%s' in block '%s'.\n'%s' has a " +
                                "fixed size  of '%s'.\nTo change its " +
                                "size you must change its Field.") %
                               (desc.get('NAME', attr_index),
                                self_desc.get('NAME', UNNAMED),
                                field, field.size, attr_name))

        if isinstance(size, int):
            # Because literal descriptor sizes are supposed to be static
            # (unless you're changing the structure), we don't even try to
            # change the size if the new size is less than the current one.
            if new_value is None and newsize <= size:
                return
            raise DescEditError("Changing a size statically defined in a " +
                                "descriptor is not supported through " +
                                "set_size. Use the 'set_desc' method instead.")

        # if a new size wasnt provided then it needs to be calculated
        if new_value is not None:
            newsize = new_value
        else:
            newsize = desc['TYPE'].sizecalc(parent=self, block=block,
                                            attr_index=attr_index)

        if isinstance(size, str):
            # set size by traversing the tag structure
            # along the path specified by the string
            self.set_neighbor(size, newsize, block)
        elif hasattr(size, "__call__"):
            # set size by calling the provided function
            size(attr_index=attr_index, new_value=newsize,
                 parent=self, block=block, **context)
        else:
            raise TypeError(("Size specified in '%s' is not a valid type." +
                             "Expected int, str, or function. Got %s.\n") %
                            (desc.get('NAME', attr_index), type(size)) +
                            "Cannot determine how to set the size.")

    def rebuild(self, **kwargs):
        '''
        Rebuilds this WhileBlock in the way specified by the keyword arguments.

        If rawdata or a filepath is supplied, it will be used to rebuild
        this WhileBlock. If not, and initdata is supplied, it will be
        used to replace the entries in this WhileBlock.

        If rawdata, initdata, filepath, and init_attrs are all unsupplied,
        all entries in this array will be deleted and replaced with new ones.

        If rawdata, initdata, and filepath are all unsupplied or
        None and init_attrs is False, this method will do nothing.

        If this WhileBlock also has a CHILD attribute, it will be
        initialized in the same way as the array elements.

        If attr_index is supplied, the initialization will only be
        done to only the specified attribute or array element.

        Raises AssertionError if initdata has no __iter__ or __len__ methods.
        Raises TypeError if rawdata and filepath are both supplied.
        Raises TypeError if rawdata doesnt have read, seek, and peek methods.
        
        Optional keywords arguments:
        # bool:
        init_attrs --- Whether or not to clear the contents of the WhileBlock.
                       Defaults to True. If True, and 'rawdata' and 'filepath'
                       are None, all the cleared array elements will be rebuilt
                       using the desciptor in this Blocks SUB_STRUCT entry.

        # buffer:
        rawdata ------ A peekable buffer that will be used for rebuilding
                       elements of this WhileBlock. Defaults to None.
                       If supplied, do not supply 'filepath'.

        # int:
        root_offset -- The root offset that all rawdata reading is done from.
                       Pointers and other offsets are relative to this value.
                       Passed to the reader of each elements Field when they
                       are rebuilt using the given filepath or rawdata.
        offset ------- The initial offset that rawdata reading is done from.
                       Passed to the reader of each elements Field when they
                       are rebuilt using the given filepath or rawdata.

        # int/str:
        attr_index --- The specific attribute index to initialize. Operates on
                       all indices if unsupplied or None. Defaults to None.

        # iterable:
        initdata ----- An iterable of Blocks to be placed into this WhileBlock.

        #str:
        filepath ----- An absolute path to a file to use as rawdata to rebuild
                       this WhileBlock. If supplied, do not supply 'rawdata'.
        '''
        attr_index = kwargs.pop('attr_index', None)
        desc = object.__getattribute__(self, "desc")

        rawdata = get_rawdata(**kwargs)

        if attr_index is not None:
            # reading/initializing just one attribute
            if isinstance(attr_index, str):
                attr_index = desc['NAME_MAP'][attr_index]

            attr_desc = desc[attr_index]

            if 'initdata' in kwargs:
                # if initdata was provided for this attribute
                # then just place it in this WhileBlock.
                self[attr_index] = kwargs['initdata']
            elif rawdata or kwargs.get('init_attrs', False):
                # we are either reading the attribute from rawdata or nothing
                kwargs.update(desc=attr_desc, parent=self,
                              rawdata=rawdata, attr_index=attr_index)
                kwargs.pop('filepath', None)
                attr_desc['TYPE'].reader(**kwargs)
            return

        old_len = len(self)
        if kwargs.get('init_attrs', True):
            # reading/initializing all array elements, so clear the block
            list.__delitem__(self, slice(None, None, None))


        # if an initdata was provided, make sure it can be used
        initdata = kwargs.pop('initdata', None)
        assert (initdata is None or
                (hasattr(initdata, '__iter__') and
                 hasattr(initdata, '__len__'))), (
                     "initdata must be an iterable with a length")

        if rawdata is not None:
            # rebuild the structure from raw data
            try:
                # we are either reading the attribute from rawdata or nothing
                kwargs.update(desc=desc, parent=self, rawdata=rawdata)
                kwargs.pop('filepath', None)
                desc['TYPE'].reader(**kwargs)
            except Exception as e:
                a = e.args[:-1]
                e_str = "\n"
                try:
                    e_str = e.args[-1] + e_str
                except IndexError:
                    pass
                e.args = a + (e_str + "Error occurred while " +
                              "attempting to rebuild %s." % type(self),)
                raise e
        elif initdata is not None:
            # initdata is not None, so use it to populate the WhileBlock
            list.extend(self, [None]*(len(initdata) - len(self)))
            for i in range(len(initdata)):
                self[i] = initdata[i]

            # if the initdata has a CHILD block, copy it to
            # this block if this block can hold a CHILD.
            try:
                self.CHILD = initdata.CHILD
            except AttributeError:
                pass
        elif kwargs.get('init_attrs', True):
            # this ListBlock is an array, so the Field
            # of each element should be the same
            try:
                attr_desc = desc['SUB_STRUCT']
                attr_field = attr_desc['TYPE']
            except Exception:
                raise TypeError("Could not locate the sub-struct descriptor." +
                                "\nCould not initialize array")

            # if initializing the array elements, extend this block with
            # elements so its length is what it was before it was cleared.
            list.extend(self, [None]*(old_len - len(self)))

            # loop through each element in the array and initialize it
            for i in range(old_len):
                attr_field.reader(attr_desc, self, None, i)

            # only initialize the child if the block has a child
            c_desc = desc.get('CHILD')
            if c_desc:
                c_desc['TYPE'].reader(c_desc, self, None, 'CHILD')


class PWhileBlock(WhileBlock):
    '''
    A subclass of WhileBlock which adds a slot for a CHILD attribute.

    Uses __init__, __sizeof__, __setattr__, and __delattr__ from PListBlock.

    See supyr_struct.blocks.while_block.WhileBlock.__doc__ for more help.
    '''
    __slots__ = ('CHILD')

    __init__ = PListBlock.__init__

    __sizeof__ = PListBlock.__sizeof__

    __setattr__ = PListBlock.__setattr__

    __delattr__ = PListBlock.__delattr__

WhileBlock.PARENTABLE = PWhileBlock
WhileBlock.UNPARENTABLE = WhileBlock

WhileBlock.PARENTABLE = PWhileBlock
WhileBlock.UNPARENTABLE = WhileBlock