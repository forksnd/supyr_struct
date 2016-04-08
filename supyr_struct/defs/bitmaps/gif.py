'''
gif image file

Structures were pieced together from various online sources
'''

from math import log
from struct import unpack
from pprint import pprint

from supyr_struct.defs.tag_def import *
from supyr_struct.field_methods import *

com = combine

def get(): return gif_def

def lzw_reader(self, desc, parent, rawdata=None, attr_index=None,
               root_offset=0, offset=0, **kwargs):
    assert parent is not None and attr_index is not None,\
           "'parent' and 'attr_index' must be provided and "+\
           "not None when reading a 'data' Field."
    
    if rawdata is not None:
        #first byte is irrelevant to deducing the size, so add 1 to the offset
        start = root_offset + offset
        rawdata.seek(start + 1)
        blocksize = int.from_bytes(rawdata.read(1), byteorder='little')
        size = blocksize + 2
        
        while blocksize > 0:
            rawdata.seek(start+size)
            blocksize = rawdata.read(1)
            if not blocksize:
                break
            blocksize = int.from_bytes(blocksize, byteorder='little')
            size += blocksize + 1
        
        rawdata.seek(start)
        #read and store the variable
        parent[attr_index] = self.decoder(rawdata.read(size),parent,attr_index)
        return offset + size
    else:
        parent[attr_index] = self.default()
        return offset

def color_table_size(block=None, parent=None, attr_index=None,
                     rawdata=None, new_value=None, *args, **kwargs):
    '''Used for calculating the size of the color table bytes'''

    if parent is None:
        raise KeyError("Cannot calculate or set the size of GIF "+
                       "Color Table without a supplied parent.")
    flags = parent.flags
    if new_value is None:
        if not flags.color_table:
            return 0
        return 3*(2**(1 + flags.color_table_size))
    
    if new_value > 3:
        flags.color_table_size = int(log((new_value//3),2)-1)
        return
    flags.color_table_size = 0

def has_next_data_block(block=None, parent=None, attr_index=None,
                        rawdata=None, new_value=None, *args, **kwargs):    
    try:
        return rawdata.peek(1) != b';'
    except AttributeError:
        return False

def get_data_block(block=None, parent=None, attr_index=None,
                   rawdata=None, new_value=None, *args, **kwargs):
    try:
        data = rawdata.peek(1)
        if len(data):
            return int.from_bytes(data, byteorder='little')
    except AttributeError:
        pass
    return

def get_block_extension(block=None, parent=None, attr_index=None,
                        rawdata=None, new_value=None, *args, **kwargs):
    
    try:
        data = rawdata.peek(2)
        if len(data) < 2:
            return
        return int.from_bytes(data[1:2], byteorder='little')
    except AttributeError:
        pass
    return

BytearrayLZW = Field( name="BytearrayLZW", default=bytearray(), endian='=',
                      raw=True, oe_size=True, sizecalc=len_sizecalc,
                      reader=lzw_reader, writer=bytes_writer)

block_sentinel = UEnum8("sentinel",
    ('extension',   33),
    ('image',       44),
    DEFAULT=33, EDITABLE=False
    )

block_delim = UInt8( "block_delimiter", MIN=0, MAX=0,
                     EDITABLE=False, VISIBLE=False )

ext_label = UEnum8( "label",
    ('plaintext_extension',   1),
    ('gfx_control_extension', 249),
    ('comment_extension',     254),
    ('application_extension', 255),
    EDITABLE=False
    )

ext_byte_size = UInt8("byte_size", EDITABLE=False)

#make modified varients of the above descriptors
#which specify different default values for each
ext_block_sentinel   = dict(block_sentinel, DEFAULT=33)
image_block_sentinel = dict(block_sentinel, DEFAULT=44)

plaintext_ext_label   = dict(ext_label, DEFAULT=1)
gfx_ext_label         = dict(ext_label, DEFAULT=249)
comment_ext_label     = dict(ext_label, DEFAULT=254)
app_ext_label         = dict(ext_label, DEFAULT=255)

plaintext_ext_byte_size = dict(ext_byte_size, DEFAULT=12)
app_ext_byte_size       = dict(ext_byte_size, DEFAULT=11)


unknown_extension = Container("unknown_extension",
    ext_block_sentinel,
    ext_label,
    ext_byte_size,

    BytesRaw("unknown_body", SIZE=".byte_size"),
    block_delim
    )

plaintext_extension = Container("plaintext_extension",
    ext_block_sentinel,
    plaintext_ext_label,
    plaintext_ext_byte_size,

    LUInt16("text_grid_left"),
    LUInt16("text_grid_top"),
    LUInt16("text_grid_width"),
    LUInt16("text_grid_height"),
    UInt8("char_cell_width"),
    UInt8("char_cell_height"),
    UInt8("fg_color_index"),
    UInt8("bg_color_index"),
    UInt8("string_length"),
    StrRawAscii("plaintext_string",SIZE='.string_length'),
    block_delim
    )

gfx_extension = Container("gfx_control_extension",
    ext_block_sentinel,
    gfx_ext_label,
    ext_byte_size,

    LBitStruct("flags",
        Bit('transparent'),
        Bit('user_input'),
        BitUInt('disposal_method', SIZE=3)
        ),
    LUInt16("delay_time"),
    UInt8("transparent_color_index"),
    block_delim
    )

comment_extension = Container( "comment_extension",
    ext_block_sentinel,
    comment_ext_label,
    ext_byte_size,

    StrRawAscii("comment_string", SIZE='.byte_size'),
    block_delim
    )

app_extension = Container("application_extension",
    ext_block_sentinel,
    app_ext_label,
    app_ext_byte_size,

    StrRawAscii("application_id", SIZE='.byte_size'),
    UInt8("data_length"),
    BytesRaw("application_data", SIZE='.data_length'),
    block_delim
    )

image_block = Container("image_block",
    image_block_sentinel,

    LUInt16("left"),
    LUInt16("top"),
    LUInt16("width"),
    LUInt16("height"),
    LBitStruct("flags",
        BitUInt("color_table_size", SIZE=3),
        Pad(2),
        Bit("sort"),
        Bit("interlace"),
        Bit("color_table")
        ),
    BytearrayRaw("local_color_table", SIZE=color_table_size),
    BytearrayLZW("image_data")
    )

block_extension = Switch( "block_extension",
    DEFAULT=unknown_extension,
    CASE=get_block_extension,
    CASES={ 0:unknown_extension,
            1:plaintext_extension,
            249:gfx_extension,
            254:comment_extension,
            255:app_extension
            }
    )


data_block = Switch( "data_block",
    DEFAULT=unknown_extension,
    CASE=get_data_block,
    CASES={ 33:block_extension,
            44:image_block }
    )

gif_header = Struct( "gif_header",
    LUInt24("gif_sig", DEFAULT='GIF'),
    LUEnum24("version",
        ("Ver_87a", 'a78'),
        ("Ver_89a", 'a98'),
        DEFAULT='a98'
        )
    )

gif_logical_screen = Container( "gif_logical_screen",
    LUInt16("canvas_width"),
    LUInt16("canvas_height"),
    LBitStruct("flags",
        BitUInt("color_table_size", SIZE=3),
        Bit("sort"),
        BitUInt("color_resolution", SIZE=3),
        Bit("color_table")
        ),
    UInt8("bg_color_index"),
    UInt8("aspect_ratio"),
    BytearrayRaw("global_color_table", SIZE=color_table_size)
    )

gif_def = TagDef( gif_header,
    gif_logical_screen,
    WhileArray("data_blocks",
        SUB_STRUCT=data_block,
        CASE=has_next_data_block
        ),
    UInt8("trailer",
        MIN=59, MAX=59, DEFAULT=';',
        EDITABLE=False, VISIBLE=False
        ),
    NAME="gif_image",

    def_id="gif", ext=".gif" )