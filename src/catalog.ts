import {t} from './i18n';
import raw from './data/settings.json';
import inputDefaults from './data/input-defaults.json';
import type {Definition,Category} from './types';
export const recommendedKeys:Record<string,string>=inputDefaults;
export const definitions=raw.map(d=>({...d,default:recommendedKeys[d.key]??d.default})) as Definition[];
export const defs=new Map(definitions.map(x=>[x.key,x]));
export const systems:Record<string,string>={auto:'Tự nhận diện',nes:'Nintendo / Famicom',snes:'Super Nintendo',snes_faust:'SNES · Faust',gb:'Game Boy / Color',gba:'Game Boy Advance',psx:'PlayStation',ss:'Sega Saturn',pce:'PC Engine / CD',pce_fast:'PC Engine · Fast',pcfx:'PC-FX',md:'Mega Drive',sms:'Master System',gg:'Game Gear',ngp:'Neo Geo Pocket',wswan:'WonderSwan',vb:'Virtual Boy',lynx:'Atari Lynx',apple2:'Apple II',ssfplay:'Nhạc Sega Saturn',sasplay:'Nhạc Sega Arcade',cdplay:'CD Audio'};
export const categories:{id:Category;label:string;subtitle:string}[]=[
 {id:'general',label:'Chung',subtitle:'Giao diện và chương trình Mednafen'},
 {id:'video',label:'Hình ảnh',subtitle:'Màn hình, tỷ lệ, độ mượt và bộ lọc'},
 {id:'audio',label:'Âm thanh',subtitle:'Âm lượng, chất lượng và độ trễ'},
 {id:'input',label:'Điều khiển',subtitle:'Bàn phím, tay cầm và phím tắt'},
 {id:'bios',label:'BIOS & firmware',subtitle:'Chọn và kiểm tra tệp khởi động'},
 {id:'saves',label:'Lưu game',subtitle:'Tự lưu, tua lại và ảnh chụp'},
 {id:'folders',label:'Thư mục',subtitle:'Nơi lưu dữ liệu của bạn'},
 {id:'system',label:'Theo hệ máy',subtitle:'Các lựa chọn riêng cho từng máy'},
 {id:'network',label:'Chơi qua mạng',subtitle:'Máy chủ và thông tin kết nối'},
 {id:'advanced',label:'Tất cả thiết lập',subtitle:'Danh mục đầy đủ của Mednafen 1.32.1'},
];
type Copy={label:string;help:string;options?:Record<string,string>};
export const friendly:Record<string,Copy>={
 'video.fs':{label:'Chơi toàn màn hình',help:'Mở game phủ toàn bộ màn hình. Có thể đổi trong lúc chơi bằng Alt + Enter.'},
 'video.driver':{label:'Cách hiển thị hình ảnh',help:'Tự động phù hợp với hầu hết máy. Dùng OpenGL để bật các bộ lọc hình ảnh.',options:{default:'Tự động (khuyên dùng)',opengl:'OpenGL · hỗ trợ bộ lọc',softfb:'Phần mềm · khi OpenGL có lỗi'}},
 'video.glvsync':{label:'Chống xé hình (VSync)',help:'Đồng bộ hình ảnh với màn hình. Tắt có thể giảm độ trễ nhưng dễ thấy đường xé hình.'},
 'video.deinterlacer':{label:'Xử lý hình ảnh xen kẽ',help:'Chỉ tác động khi game xuất hình xen kẽ. Giữ mặc định nếu hình ảnh đang bình thường.',options:{weave:'Ghép hai trường hình (mặc định)',bob:'Nhân đôi từng trường hình',blend:'Trộn hai trường hình',blend_rg:'Trộn và giảm bóng mờ'}},
 'fps.autoenable':{label:'Hiện số khung hình (FPS)',help:'Hiện thông tin tốc độ khi mở game. Dùng để kiểm tra game có chạy đúng tốc độ hay không.'},
 'sound':{label:'Bật âm thanh',help:'Phát âm thanh trong game.'},
 'sound.volume':{label:'Âm lượng (%)',help:'100% là âm lượng gốc. Cao hơn 100% có thể làm âm thanh bị rè.'},
 'sound.rate':{label:'Tần số âm thanh (Hz)',help:'48.000 Hz phù hợp với phần lớn thiết bị. Tăng cao hơn thường không giúp game retro nghe hay hơn.'},
 'sound.driver':{label:'Thiết bị phát âm thanh',help:'Tự động dùng cách phát phù hợp với Windows. WASAPI riêng có độ trễ thấp nhưng có thể chiếm thiết bị âm thanh.',options:{default:'Tự động (khuyên dùng)',wasapish:'WASAPI · dùng chung',dsound:'DirectSound · tương thích',wasapi:'WASAPI · chế độ riêng',sdl:'SDL · phương án dự phòng'}},
 'sound.buffer_time':{label:'Bộ đệm âm thanh (ms)',help:'0 = tự động. Nếu âm thanh lách tách, thử tăng lên 40–60 ms; bộ đệm lớn làm âm thanh trễ hơn.'},
 'sound.device':{label:'Mã thiết bị âm thanh',help:'Giữ “default” để dùng thiết bị mặc định của Windows. Chỉ đổi nếu bạn biết mã thiết bị của driver.'},
 'sound.period_time':{label:'Chu kỳ xử lý âm thanh (µs)',help:'0 = tự động. Đây là thiết lập chuyên sâu, phụ thuộc driver âm thanh.'},
 'autosave':{label:'Tự lưu và tiếp tục lần chơi trước',help:'Lưu trạng thái khi thoát game bình thường, rồi tự tải khi mở lại. Vẫn nên lưu bằng menu trong game để có bản lưu lâu dài.'},
 'srwframes':{label:'Số khung hình giữ để tua lại',help:'600 khung tương đương khoảng 10 giây với game 60 FPS. Giá trị cao dùng nhiều RAM hơn. Bật tua lại trong game bằng Alt + S.'},
 'ffspeed':{label:'Tốc độ tua nhanh',help:'4 = chạy nhanh gấp bốn lần khi giữ phím tua nhanh. Tốc độ thực tế tùy cấu hình máy.'},
 'fftoggle':{label:'Nhấn một lần để bật/tắt tua nhanh',help:'Khi tắt, bạn phải giữ phím tua nhanh; khi bật, nhấn lần nữa để trở về tốc độ thường.'},
 'sfspeed':{label:'Tốc độ chạy chậm',help:'0,75 = chạy ở 75% tốc độ gốc khi dùng phím chạy chậm.'},
 'filesys.state_comp_level':{label:'Nén bản lưu trạng thái',help:'Mức 6 cân bằng tốc độ và dung lượng. -1 tắt nén, 9 nén tối đa.'},
 'filesys.path_sav':{label:'Bản lưu trong game / thẻ nhớ',help:'Nơi lưu tiến trình từ menu Save trong game, thẻ nhớ và bộ nhớ máy.'},
 'filesys.path_state':{label:'Bản lưu nhanh (save state)',help:'Nơi lưu trạng thái tức thời khi nhấn F1. Đây là loại tệp khác với bản lưu trong game.'},
 'filesys.path_savbackup':{label:'Bản sao lưu tự động',help:'Nơi Mednafen giữ bản dự phòng của dữ liệu lưu trong game.'},
 'filesys.path_snap':{label:'Ảnh chụp màn hình',help:'Nơi lưu ảnh PNG chụp bằng F9 hoặc Shift + F9.'},
 'filesys.path_firmware':{label:'Thư mục BIOS / firmware',help:'Mednafen tìm các tệp khởi động tại đây. Bạn cũng có thể chọn tệp BIOS riêng trong mục BIOS & firmware.'},
 'filesys.path_cheat':{label:'Mã cheat',help:'Nơi lưu mã cheat theo game.'},
 'filesys.path_movie':{label:'Bản ghi thao tác chơi',help:'Bản ghi đầu vào để Mednafen phát lại; đây không phải video thông thường.'},
 'filesys.path_palette':{label:'Bảng màu tùy chỉnh',help:'Nơi đặt các tệp palette cho những hệ máy có hỗ trợ.'},
 'filesys.path_pgconfig':{label:'Cấu hình ghi đè ngoài ứng dụng',help:'Các tệp per-game đặt ở đây có thể ghi đè lựa chọn trong ứng dụng. Thông thường bạn nên dùng bộ chọn “Áp dụng cho” ở phía trên.'},
 'input.joystick.axis_threshold':{label:'Ngưỡng cần analog (%)',help:'Cần phải nghiêng bao nhiêu để được tính là một lần bấm hướng. Giảm nếu cần nghiêng quá sâu mới nhận.'},
 'input.ckdelay':{label:'Giữ phím trước thao tác quan trọng (ms)',help:'Tránh vô tình Reset hoặc thoát game. Ví dụ 500 yêu cầu giữ phím trong nửa giây.'},
 'input.grab.strategy':{label:'Giữ bàn phím và chuột trong game',help:'Chỉ có tác dụng khi bật chế độ giữ đầu vào trong Mednafen. Tự động giúp hạn chế khóa các phím hệ điều hành.',options:{auto:'Tự động theo thiết bị giả lập',full:'Giữ cả bàn phím và chuột',kb_auto:'Bàn phím tự động, luôn giữ chuột',mouse_auto:'Chuột tự động, luôn giữ bàn phím'}},
 'input.joystick.global_focus':{label:'Nhận tay cầm khi game ở nền',help:'Game vẫn nhận nút tay cầm dù bạn đang chọn cửa sổ khác.'},
 'cd.image_memcache':{label:'Nạp đĩa CD vào RAM',help:'Có thể giảm giật do đọc đĩa, nhưng tăng thời gian mở game và lượng RAM sử dụng. Cần bật nếu chơi CD nằm trong ZIP.'},
 'netplay.host':{label:'Địa chỉ máy chủ',help:'Máy chủ Mednafen Netplay mà những người chơi cùng kết nối.'},
 'netplay.port':{label:'Cổng máy chủ',help:'Mặc định 4046. Chỉ đổi khi người quản lý máy chủ yêu cầu.'},
 'netplay.nick':{label:'Tên hiển thị',help:'Tên của bạn trong phòng chơi và chat.'},
 'netplay.password':{label:'Mật khẩu máy chủ',help:'Để trống nếu máy chủ không yêu cầu. Giá trị này được lưu trong tệp cấu hình trên máy.'},
 'netplay.gamekey':{label:'Mã nhóm chơi',help:'Những người dùng cùng bản game và mã nhóm sẽ được ghép cùng phiên.'},
 'netplay.localplayers':{label:'Số người chơi trên máy này',help:'Số tay cầm / người chơi cục bộ bạn muốn đưa vào phiên mạng.'},
 'psx.region_autodetect':{label:'Tự nhận diện vùng PlayStation',help:'Tự chọn Nhật, Mỹ hoặc châu Âu từ đĩa game. Nên bật.'},
 'ss.region_autodetect':{label:'Tự nhận diện vùng Saturn',help:'Tự chọn vùng máy dựa trên game. Nên bật.'},
 'psx.region_default':{label:'Vùng PlayStation dự phòng',help:'Chỉ dùng nếu không nhận diện được vùng đĩa.'},
 'ss.region_default':{label:'Vùng Saturn dự phòng',help:'Chỉ dùng nếu không nhận diện được vùng đĩa.'},
 'psx.bios_jp':{label:'PlayStation · Nhật',help:'BIOS SCPH-5500 / v3.0J. Tệp gợi ý: scph5500.bin.'},
 'psx.bios_na':{label:'PlayStation · Mỹ',help:'BIOS SCPH-5501 / v3.0A. Tệp gợi ý: scph5501.bin.'},
 'psx.bios_eu':{label:'PlayStation · châu Âu',help:'BIOS SCPH-5502 / v3.0E. Tệp gợi ý: scph5502.bin.'},
 'ss.bios_jp':{label:'Sega Saturn · Nhật',help:'Tệp BIOS gợi ý: sega_101.bin.'},
 'ss.bios_na_eu':{label:'Sega Saturn · Mỹ / châu Âu',help:'Tệp BIOS gợi ý: mpr-17933.bin.'},
 'pce.cdbios':{label:'PC Engine CD · System Card',help:'Thường dùng System Card 3.0 (syscard3.pce). Game HuCard thường không cần tệp này.'},
 'pcfx.bios':{label:'PC-FX',help:'Tệp khởi động cho PC-FX, thường là pcfx.rom.'},
 'gba.bios':{label:'Game Boy Advance',help:'Để trống để dùng mô phỏng BIOS tích hợp; chọn BIOS thật khi game có yêu cầu.'},
 'command.save_state':{label:'Lưu nhanh',help:'Chụp trạng thái game vào ô lưu đang chọn. Mặc định F1.'},
 'command.load_state':{label:'Tải bản lưu nhanh',help:'Quay lại trạng thái đã lưu trong ô đang chọn. Mặc định F2.'},
 'command.exit':{label:'Thoát game',help:'Thoát Mednafen bình thường và trở về thư viện. Mặc định F12.'},
 'command.toggle_fs':{label:'Đổi toàn màn hình',help:'Chuyển giữa cửa sổ và toàn màn hình. Mặc định Alt + Enter.'},
 'command.pause':{label:'Tạm dừng',help:'Tạm dừng hoặc tiếp tục game.'},
 'command.fast_forward':{label:'Tua nhanh',help:'Tăng tốc game theo mức trong mục Lưu game.'},
 'command.state_slot_inc':{label:'Next save slot',help:'F3 selects the next save slot. This does not save or load a state.'},
 'command.state_slot_dec':{label:'Previous save slot',help:'Shift + F3 selects the previous save slot.'},
 'command.take_snapshot':{label:'Chụp màn hình',help:'Lưu ảnh PNG vào thư mục ảnh chụp.'},
};
function rawCopyFor(d:Definition):Copy{
 if(friendly[d.key])return friendly[d.key];
 const suffix=d.key.split('.').slice(1).join('.');
 const templates:Record<string,Copy>={
  stretch:{label:'Tỷ lệ khi toàn màn hình',help:'Giữ đúng tỷ lệ giúp nhân vật không bị kéo ngang. Phóng theo số nguyên giữ các điểm ảnh đều nhau.',options:{'0':'Không kéo giãn',full:'Lấp đầy màn hình',aspect:'Giữ đúng tỷ lệ',aspect_int:'Đúng tỷ lệ, điểm ảnh đều',aspect_mult2:'Đúng tỷ lệ, phóng bội số 2'}},
  shader:{label:'Bộ lọc hình ảnh',help:'Thay đổi cách hiển thị pixel. Các bộ lọc này cần OpenGL.',options:{none:'Nguyên bản · không lọc',autoip:'Tự làm mượt',autoipsharper:'Sắc nét',scale2x:'Scale2x · mượt cạnh',sabr:'SABR · mượt nét',ipsharper:'Nội suy sắc nét',goat:'TV CRT · màn hình cổ'}},
  videoip:{label:'Làm mượt điểm ảnh',help:'Tắt để pixel rõ cạnh. Bộ lọc shader sẽ được ưu tiên nếu đã bật.',options:{'0':'Tắt · pixel rõ','1':'Làm mượt hai chiều',x:'Chỉ chiều ngang',y:'Chỉ chiều dọc'}},
  scanlines:{label:'Độ đậm dòng quét (%)',help:'0 = không hiện dòng quét. Giá trị cao tạo các sọc tối giống TV cổ.'},
  xscale:{label:'Phóng ngang trong cửa sổ',help:'Số lần phóng chiều ngang của hình ảnh game.'},
  yscale:{label:'Phóng dọc trong cửa sổ',help:'Số lần phóng chiều dọc của hình ảnh game.'},
  xscalefs:{label:'Phóng ngang khi toàn màn hình',help:'Dùng khi tắt kéo giãn tự động.'},
  yscalefs:{label:'Phóng dọc khi toàn màn hình',help:'Dùng khi tắt kéo giãn tự động.'},
  special:{label:'Bộ lọc phần mềm',help:'Bộ lọc chạy bằng CPU; thường giữ “none” và dùng bộ lọc hình ảnh ở trên.'},
  enable:{label:'Cho phép tự nhận diện hệ máy này',help:'Tắt để Mednafen không tự chọn module này khi mở game.'},
 };
 if(templates[suffix])return templates[suffix];
 if(/\.input\.port\d+$/.test(d.key))return {label:t('Thiết bị giả lập · cổng ')+d.key.match(/port(\d+)/)![1],help:'Chọn loại tay cầm mà game nhìn thấy. Gamepad thường tương thích nhất.'};
 if(d.flags.includes('MDFNSF_CAT_INPUT_MAPPING')){const name=d.key.split('.').at(-1)!;const labels:Record<string,string>={up:'Lên',down:'Xuống',left:'Trái',right:'Phải',start:'Start',select:'Select',rapid_a:'A liên thanh',rapid_b:'B liên thanh',square:'Vuông',triangle:'Tam giác',circle:'Tròn',cross:'Chéo'};return{label:labels[name]??name.toUpperCase(),help:'Gán phím bàn phím cho nút này. Dùng hướng dẫn bên dưới để gán tay cầm.'};}
 return{label:d.key,help:d.description};
}
export function keysFor(category:Category,system:string){
 const keys:Record<string,string[]>={general:['autosave','video.fs'],video:['video.fs','video.driver','video.glvsync',...['stretch','shader','videoip','scanlines','xscale','yscale'].map(k=>`${system}.${k}`),'video.deinterlacer','fps.autoenable'],audio:['sound','sound.volume','sound.rate','sound.driver','sound.buffer_time','sound.device','sound.period_time'],input:[`${system}.input.port1`,'input.joystick.axis_threshold','input.ckdelay','input.joystick.global_focus','input.grab.strategy'],saves:['autosave','srwframes','ffspeed','fftoggle','sfspeed','filesys.state_comp_level'],network:['netplay.host','netplay.port','netplay.nick','netplay.password','netplay.gamekey','netplay.localplayers']};
 if(category==='bios')return definitions.filter(d=>d.type==='string'&&(d.key.includes('bios')||d.key.includes('firmware'))&&!d.key.startsWith('filesys.')).map(d=>d.key);
 if(category==='folders')return definitions.filter(d=>d.key.startsWith('filesys.path_')).map(d=>d.key);
 if(category==='system')return definitions.filter(d=>d.key.startsWith(system+'.')&&!d.key.includes('.input.')&&!d.flags.includes('MDFNSF_SUPPRESS_DOC')).map(d=>d.key);
 return(keys[category]??[]).filter(k=>defs.has(k));
}

export function copyFor(d:Definition):Copy{
 const c=rawCopyFor(d);
 return {...c,label:t(c.label),help:t(c.help),options:c.options?Object.fromEntries(Object.entries(c.options).map(([key,value])=>[key,t(value)])):undefined};
}
